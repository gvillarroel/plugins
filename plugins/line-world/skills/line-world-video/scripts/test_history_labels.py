#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Check history endpoint labels in the generated linked composition."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

from inspect_focus import browser_path
from line_world import build


class HistoryLabelsTest(unittest.TestCase):
    def test_stable_history_labels_have_clearance_and_margin(self):
        evidence = os.environ.get("LINE_WORLD_HISTORY_EVIDENCE")
        with tempfile.TemporaryDirectory() as temporary, sync_playwright() as playwright:
            root = Path(evidence or temporary).resolve()
            browser = playwright.chromium.launch(executable_path=browser_path(), headless=True)
            page = browser.new_page(viewport={"width": 960, "height": 540})
            for case in ("default", "revisión"):
                with self.subTest(case=case):
                    project = root / case
                    subprocess.run([
                        sys.executable, str(Path(__file__).with_name("line_world.py")),
                        "init", "--project", str(project),
                    ], check=True, capture_output=True)
                    if case == "revisión":
                        source = project / "story.json"
                        story = json.loads(source.read_text(encoding="utf-8"))
                        story["rows"][1]["label"] = "Revisión técnica final"
                        source.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
                        build(project)
                    page.goto((project / "index.html").as_uri())
                    page.evaluate("async () => { await window.ready; }")
                    readings = page.evaluate("""() => {
                        const history = STORY.beats.find(beat => beat.id === 'history');
                        return STORY.rows.map((row, index) => {
                            const time = history.start + (index + .9) * history.duration / STORY.rows.length;
                            renderAt(time);
                            const label = document.querySelector(`.history-label[data-row-id="${row.id}"]`);
                            const endpoint = document.querySelector('[data-motion-id="selected-history-reading"]');
                            const box = label.getBoundingClientRect();
                            const point = endpoint.getBoundingClientRect();
                            return {id: row.id, text: label.textContent, time,
                                visible: getComputedStyle(label).visibility === 'visible',
                                frameMargin: innerWidth - box.right, dataClearance: box.left - point.right};
                        });
                    }""")
                    if evidence:
                        review = readings[1]
                        page.evaluate("time => renderAt(time)", review["time"])
                        page.screenshot(path=str(project / "history.png"))
                        (project / "geometry.json").write_text(
                            json.dumps(readings, ensure_ascii=False, indent=2), encoding="utf-8",
                        )
                    self.assertEqual([row["text"] for row in readings], [
                        "Intake · 12", "Revisión técnica final · 8" if case == "revisión" else "Review · 8",
                        "Build · 16", "Release · 6",
                    ])
                    for reading in readings:
                        self.assertTrue(reading["visible"], reading)
                        self.assertGreaterEqual(reading["frameMargin"], 24, reading)
                        self.assertGreaterEqual(reading["dataClearance"], 4, reading)


if __name__ == "__main__":
    unittest.main()
