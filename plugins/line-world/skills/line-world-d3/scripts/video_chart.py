#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Build, seek and export a measured offline D3 comparison or dated series."""
import argparse
import base64
from datetime import date
from html import escape
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL / "assets/templates/video-chart.html"


def check_data(raw):
    if not isinstance(raw, dict):
        raise ValueError("Provide a JSON object.")
    def label(key, limit, obj=raw):
        value = obj.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(f"{key} must contain 1–{limit} characters.")

    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value):
            raise ValueError("Use lowercase entity IDs starting with a letter.")
        return value

    def observation(row):
        if "value" not in row:
            raise ValueError("Provide a value or explicit null for each observation.")
        v = row["value"]
        if v is not None and (isinstance(v, bool) or not isinstance(v, (float, int))
                              or not math.isfinite(v) or abs(v) > 1e9):
            raise ValueError("Provide a finite value in [-1e9, 1e9], or null.")

    label("unit", 48)
    if "title" in raw:
        label("title", 84)
    if "signed" in raw and not isinstance(raw["signed"], bool):
        raise ValueError("signed must be true or false.")
    if "locale" in raw and not re.fullmatch(r"[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*", str(raw["locale"])):
        raise ValueError("Use a language tag such as es-ES or en-US.")
    duration = raw.setdefault("duration", 8)
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 2:
        raise ValueError("Duration must be finite and at least two seconds.")
    kind = raw.get("kind", "comparison")
    if kind == "comparison":
        rows = raw.get("records")
        if not isinstance(rows, list) or not 2 <= len(rows) <= 8:
            raise ValueError("Provide 2–8 comparison records.")
        ids = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Records must be objects.")
            key = identifier(row.get("id"))
            if key in ids:
                raise ValueError("Comparison IDs must be unique.")
            ids.add(key)
            label("label", 48, row)
            observation(row)
        if "focus" in raw and raw["focus"] not in ids:
            raise ValueError("The focus must be a known entity ID.")
    elif kind == "time-series":
        if "id" in raw:
            identifier(raw["id"])
        rows = raw.get("observations")
        if not isinstance(rows, list) or not 2 <= len(rows) <= 2000:
            raise ValueError("Provide 2–2000 dated observations.")
        dates = []
        for row in rows:
            if not isinstance(row, dict) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(row.get("date"))):
                raise ValueError("Provide a date in YYYY-MM-DD on every observation.")
            dates.append(date.fromisoformat(row["date"]))
            observation(row)
        if dates != sorted(set(dates)):
            raise ValueError("Observation dates must be unique and increasing.")
        if all(row["value"] is None for row in rows):
            raise ValueError("A trend needs at least one observed value.")
    else:
        raise ValueError("kind must be comparison or time-series.")
    return raw


def browser_path():
    cache = Path(os.environ.get("LOCALAPPDATA",str(Path.home()/".cache"))) / "ms-playwright"
    cached = sorted(cache.glob("chromium_headless_shell-*/chrome-headless-shell-win64/chrome-headless-shell.exe"),
                    key=lambda p:int(p.parts[-3].split("-")[-1]), reverse=True)
    options = [os.environ.get("LINE_WORLD_BROWSER"), *map(str,cached), "C:/Program Files/Google/Chrome/Application/chrome.exe",
               "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/usr/bin/chromium", "/usr/bin/google-chrome"]
    return next((p for p in options if p and Path(p).is_file()), None)


def build_project(project, data):
    if (project/"scene.html").exists():
        raise ValueError("Refusing to overwrite an existing scene.")
    project.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SKILL/"assets/vendor/d3.v7.9.0.min.js", project/"d3.min.js")
    shutil.copyfile(SKILL/"assets/vendor/D3-LICENSE.txt", project/"D3-LICENSE.txt")
    encoded = json.dumps(data, indent=2)
    (project/"data.json").write_text(encoded+"\n", encoding="utf-8")
    fonts = SKILL.parent/"line-world-video/assets/fonts"
    font_markup = ""
    if (fonts/"space-grotesk.ttf").is_file() and (fonts/"OFL.txt").is_file():
        font = base64.b64encode((fonts/"space-grotesk.ttf").read_bytes()).decode("ascii")
        licence = escape((fonts/"OFL.txt").read_text(encoding="utf-8"))
        font_markup = (f'<metadata id="chart-font-license">{licence}</metadata>'
                       '<style>@font-face{font-family:ChartSpace;font-style:normal;font-weight:300 700;'
                       f"src:url(data:font/ttf;base64,{font}) format('truetype')}}</style>")
    template=TEMPLATE.read_text(encoding="utf-8").replace("__CHART_FONT__",font_markup)
    (project/"scene.html").write_text(template.replace("__DATA__", encoded.replace("<","\\u003c")),encoding="utf-8")


def export_movie(page, target, duration, fps):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ValueError("--mp4 requires FFmpeg on the PATH.")
    target.parent.mkdir(parents=True, exist_ok=True)
    frames = math.ceil(duration * fps)
    with tempfile.TemporaryDirectory(dir=target.parent) as folder:
        movie = Path(folder)/"render.mp4"
        cmd = [ffmpeg, "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "png",
               "-i", "-", "-an", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p",
               "-movflags", "+faststart", str(movie)]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        try:
            previous, png = None, None
            for i in range(frames):
                geometry = page.evaluate("""t=>{renderAt(t);return document.querySelector('#stage .content').innerHTML}""", i/fps)
                if geometry != previous:
                    png = page.screenshot(type="png")
                    previous = geometry
                process.stdin.write(png)
            process.stdin.close()
            if process.wait():
                raise ValueError("FFmpeg failed while encoding the chart.")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        movie.replace(target)
    return {"frames":frames,"fps":fps}


def export(a, project, data):
    from playwright.sync_api import sync_playwright
    if a.width < 1 or a.height < 1 or (a.at is not None and not 0 <= a.at <= data["duration"]):
        raise ValueError("Use positive dimensions and a frame time inside the scene.")
    if a.mp4 and (a.width % 2 or a.height % 2 or not 1 <= a.fps <= 60):
        raise ValueError("MP4 needs even dimensions and 1–60 fps.")
    at = data["duration"] if a.at is None else a.at
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_path(), headless=True, args=["--disable-gpu"])
        page = browser.new_page(viewport={"width":a.width,"height":a.height})
        errors = []
        page.on("pageerror", lambda e:errors.append(str(e)))
        page.goto((project/"scene.html").as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        samples = [page.evaluate("t=>renderAt(t)", t) for t in (0,data["duration"]/4,data["duration"]/2,data["duration"])]
        page.evaluate("t=>renderAt(t)", at)
        before = page.locator("#stage").evaluate("e=>e.outerHTML")
        page.evaluate("renderAt(0)")
        page.evaluate("t=>renderAt(t)", at)
        repeat = page.locator("#stage").evaluate("e=>e.outerHTML") == before
        details = page.evaluate((SKILL/"scripts/video_chart_audit.js").read_text(encoding="utf-8"))
        motion = page.evaluate((SKILL/"scripts/video_chart_motion_audit.js").read_text(encoding="utf-8"),data["duration"])
        page.evaluate("t=>renderAt(t)", at)
        comparisons = data.get("records")
        rows = data["observations"] if comparisons is None else comparisons
        checks = {"labelsWithinFrame":not details["outside"],"pairwiseLabelClearance":not details["overlaps"],"unitsVisible":details["unitsVisible"],
                  "readableType":details["minFontPx"] >= 12,"visibleNumbers":details["visibleNumbers"],
                  "sourceValues":details["values"] == [r["value"] for r in rows],
                  "signedMarksAndGaps":details["validMarks"],"solidPaint":details["solidPaint"],
                  "repeatSeek":repeat,"noBrowserErrors":not errors,"realD3":page.evaluate("d3.version")=="7.9.0"}
        checks["sharedValueScale" if comparisons is None else "sameZeroBasedScale"] = details["scale"]
        if comparisons is None:
            checks["calendarSpacing"] = details["calendarSpacing"]
        if motion["supported"]:
            checks["focusAndMotion"] = motion["ok"]
        report = {"ok":all(checks.values()),"checks":checks,"sourceValues":rows,"unit":data["unit"],
                  "palette":"colorset1","d3Version":page.evaluate("d3.version"),"samples":samples,
                  "viewport":[a.width,a.height],"seconds":at,"motion":motion,"details":details,"errors":errors}
        for path in (a.screenshot,a.svg,a.receipt):
            path.resolve().parent.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(a.screenshot.resolve()))
        svg = page.locator("#stage").evaluate("""e=>{const c=e.cloneNode(true),v=c.viewBox.baseVal;
            c.setAttribute('width',v.width);c.setAttribute('height',v.height);
            c.setAttribute('font-family','ChartSpace, Arial, sans-serif');return new XMLSerializer().serializeToString(c)}""")
        a.svg.write_text(svg,encoding="utf-8")
        if report["ok"] and a.mp4:
            report["movie"] = export_movie(page, a.mp4, data["duration"], a.fps)
        a.receipt.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        browser.close()
    print(json.dumps({"ok":report["ok"],"checks":checks}))
    return 0 if report["ok"] else 2


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=("build","export"))
    p.add_argument("--project",type=Path,required=True)
    for key in ("data","svg","screenshot","receipt"):
        p.add_argument("--"+key,type=Path)
    p.add_argument("--width",type=int,default=1920)
    p.add_argument("--height",type=int,default=1080)
    p.add_argument("--at",type=float,help="Frame time in seconds; default is the end.")
    p.add_argument("--mp4",type=Path,help="Also render the whole chart to silent H.264 using FFmpeg.")
    p.add_argument("--fps",type=int,default=24)
    a=p.parse_args()
    project=a.project.resolve()
    if project.is_relative_to(SKILL):
        p.error("Keep generated files outside the skill.")
    if a.command=="build":
        if not a.data:
            p.error("--data is required for build.")
        data=check_data(json.loads(a.data.read_text(encoding="utf-8-sig")))
        build_project(project,data)
        print(json.dumps({"ok":True,"project":str(project),"duration":data["duration"],"palette":"colorset1"}))
        return 0
    if not all((a.svg,a.screenshot,a.receipt)):
        p.error("export requires --svg, --screenshot and --receipt.")
    if importlib.util.find_spec("playwright") is None:
        runner=shutil.which("uv")
        if not runner:
            p.error("Use uv run --script to resolve Playwright.")
        return subprocess.call([runner,"run","--script",str(Path(__file__).resolve()),*sys.argv[1:]])
    data=check_data(json.loads((project/"data.json").read_text(encoding="utf-8-sig")))
    return export(a,project,data)


if __name__=="__main__":
    raise SystemExit(main())
