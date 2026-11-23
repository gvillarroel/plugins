#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Measure independent SVG geometry at every frame of a normal Line World project."""
from __future__ import annotations

import argparse
import functools
import json
from collections import Counter
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright
from inspect_focus import browser_path


READER = r"""() => {
  const stage = document.querySelector('#stage');
  const camera = stage.querySelector('#world');
  const guide = stage.querySelector('#attention-dot, #guide-dot');
  const comparison = stage.querySelector('[data-motion-id="before-to-after"]');
  const readouts = [...stage.querySelectorAll('#paired-chart .chart-value')];
  const fields = ['x','y','x1','y1','x2','y2','width','height','cx','cy','r','rx','ry',
    'd','points','transform','stroke-width','stroke-dasharray','stroke-dashoffset'];
  const displayFields = ['display','visibility','opacity'];
  const markQuery = 'line,path,polyline,polygon,rect,circle,ellipse,[data-motion-id],[data-lw-motion-overlay]';
  const marks = [...stage.querySelectorAll(markQuery)].filter(e => !e.closest('defs') && !guide?.contains(e));
  const owners = new Map([[camera,'camera'], [guide,'guide']]);
  for (const [i, e] of marks.entries()) {
    owners.set(e,e.dataset.motionId || e.dataset.lwMotionOverlay || (e.id || e.tagName + '-' + i));
  }
  const state = new WeakMap();
  const rounded = value => value !== null && value !== '' && Number.isFinite(+value)
    ? String(Math.round(+value * 100) / 100) : value;
  function visible(element) {
    for (let e = element; e && e !== stage; e = e.parentElement) {
      if (displayFields.some(k => (e.style.getPropertyValue(k) || e.getAttribute(k)) ===
        ({display:'none', visibility:'hidden', opacity:'0'})[k])) return false;
    }
    return true;
  }
  function geometry(e) {
    const values = fields.map(name => {
      const v = e.style.getPropertyValue(name) || e.getAttribute(name);
      if (name === 'stroke-dashoffset') {
        const dash = e.style.strokeDasharray || e.getAttribute('stroke-dasharray');
        if (!dash || dash === 'none') return null;
      }
      return rounded(v);
    });
    if (e === guide && guide.tagName !== 'circle') {
      values.push(...[...guide.querySelectorAll('circle')].map(dot => rounded(dot.getAttribute('r'))));
    }
    return JSON.stringify(values);
  }
  function inspect(e) {
    return {geometry:geometry(e), visible:visible(e)};
  }
  function overlapsReadout() {
    if (!comparison || !visible(comparison)) return false;
    const box = comparison.getBoundingClientRect();
    const x = box.left + box.width / 2, y = box.top + box.height / 2, radius = box.width / 2;
    return readouts.some(e => {
      const readout = e.getBoundingClientRect();
      return readout.width > 0 && readout.height > 0 &&
        Math.hypot(x - Math.max(readout.left, Math.min(x, readout.right)),
          y - Math.max(readout.top, Math.min(y, readout.bottom))) < radius;
    });
  }
  renderAt(0);
  for (const e of owners.keys()) if (e) state.set(e,inspect(e));
  const changes = new MutationObserver(() => {});
  changes.observe(stage,{subtree:true,attributes:true,attributeOldValue:true,attributeFilter:['style',...fields,...displayFields]});
  window.measureTemplateMotion = (start, end, fps) => {
    const observed = [];
    for (let frame = start; frame < end; frame++) {
      const frameState = renderAt(frame / fps);
      const changed = new Set();
      for (const {target, attributeName, oldValue} of changes.takeRecords()) {
        if (oldValue === target.getAttribute(attributeName)) continue;
        const own = guide?.contains(target) ? guide : target;
        if (owners.has(own)) changed.add(own);
        else if (displayFields.includes(attributeName)) {
          target.querySelectorAll(markQuery).forEach(e => { if (owners.has(e)) changed.add(e); });
        }
      }
      const moving = [];
      for (const e of changed) {
        const previous = state.get(e), now = inspect(e);
        if (previous.visible && now.visible && previous.geometry !== now.geometry) moving.push(owners.get(e));
        state.set(e,now);
      }
      observed.push([frameState.beat, moving, overlapsReadout()]);
    }
    return observed;
  };
  window.finishTemplateMotion = () => {
    changes.disconnect();
    delete window.measureTemplateMotion;
    delete window.finishTemplateMotion;
    renderAt(0);
  };
}"""


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def summarize(frames, fps):
    seconds = {}
    beats = {}
    active = Counter()
    peak = 0
    for i, (beat, moving, _) in enumerate(frames):
        second = seconds.setdefault(i // fps, {"second": i // fps, "peak": 0, "movingFrames": 0})
        row = beats.setdefault(beat, {"peak": 0, "frames": 0, "quietFrames": 0, "objects": set()})
        count = len(moving)
        peak = max(peak, count)
        second["peak"] = max(second["peak"], count)
        second["movingFrames"] += bool(moving)
        row["peak"] = max(row["peak"], count)
        row["frames"] += 1
        row["quietFrames"] += not moving
        row["objects"].update(moving)
        active.update(moving)
    for row in beats.values():
        row["objects"] = sorted(row["objects"])
    readout_hits = [i for i, (_, _, overlaps) in enumerate(frames) if overlaps]
    return {
        "ok": peak <= 3 and not readout_hits and all(len(row["objects"]) >= 2 for row in beats.values()),
        "fps": fps,
        "frames": len(frames),
        "peakSimultaneous": peak,
        "framesOverThree": sum(len(moving) > 3 for _, moving, _ in frames),
        "comparisonReadoutOverlapFrames": readout_hits,
        "movingFramesByObject": dict(active),
        "beats": beats,
        "seconds": list(seconds.values()),
        "scope": "Raw SVG geometry, dash motion and stroke weight on consecutive rendered frames. "
                 "The camera and guide count once each. Color, appearing or disappearing marks and cuts "
                 "are distinct from independent translating or transforming geometry.",
    }


def inspect_page(page, fps, frames):
    page.evaluate(READER)
    sampled = []
    try:
        for start in range(0, frames, 120):
            sampled.extend(page.evaluate(
                "([start,end,fps]) => measureTemplateMotion(start,end,fps)",
                [start, min(frames, start + 120), fps],
            ))
    finally:
        page.evaluate("window.finishTemplateMotion()")
    return summarize(sampled, fps)


def inspect_project(project: Path):
    timing = json.loads((project / "timing.json").read_text(encoding="utf-8-sig"))
    project_info = json.loads((project / "story.json").read_text(encoding="utf-8-sig"))
    fps = timing["fps"]
    count = round(timing["duration"] * fps)
    handler = functools.partial(Quiet, directory=str(project))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=browser_path(), headless=True)
            try:
                page = browser.new_page(viewport={"width": project_info["width"], "height": project_info["height"]})
                page.goto(f"http://127.0.0.1:{server.server_port}/index.html")
                page.evaluate("async () => { await document.fonts.ready; await window.ready; }")
                return inspect_page(page, fps, count)
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = inspect_project(args.project)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("ok", "fps", "frames", "peakSimultaneous", "framesOverThree")}))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
