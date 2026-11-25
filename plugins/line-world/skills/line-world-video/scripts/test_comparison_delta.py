#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Check that the signed change stays with its selected pair of bars."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

from inspect_focus import browser_path
from line_world import DEFAULT


class ComparisonDeltaTests(unittest.TestCase):
    def test_delta_stays_below_each_active_pair_and_above_the_next_mark(self):
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            root = Path(temp)
            browser = playwright.chromium.launch(executable_path=browser_path())
            page = browser.new_page(viewport={"width": 960, "height": 540})
            for count in (2, 8):
                rows = [{"id": f"etapa-{i}", "label": f"Etapa {i}", "before": i + 2,
                         "after": (i * 3) % 7} for i in range(count)]
                story = {**DEFAULT, "rows": rows, "unit": "días",
                         "timing": {**DEFAULT["timing"], "compare": 2 + 2 * count}}
                source = root / "input.json"
                source.write_text(json.dumps(story), encoding="utf-8")
                project = root / str(count)
                subprocess.run([sys.executable, str(Path(__file__).with_name("line_world.py")),
                                "init", "--project", str(project), "--story", str(source)],
                               check=True, capture_output=True)
                page.goto((project / "index.html").as_uri())
                page.evaluate("window.ready")
                for scale in (0.75, 1, 1.5):
                    with self.subTest(rows=count, font_scale=scale):
                        readings = page.evaluate("""scale => {
                            document.documentElement.style.setProperty('--lw-font-scale', scale);
                            const beat = STORY.beats.find(beat => beat.id === 'compare');
                            const pairs = [...document.querySelectorAll('#paired-chart .pair')];
                            const delta = document.querySelector('#data-delta');
                            const axis = document.querySelector('#paired-chart .pair-axis');
                            return pairs.map((pair, i) => {
                                renderAt(beat.start + 3 + i * 2);
                                const box = delta.getBoundingClientRect();
                                const value = pair.querySelector('.after-bar').getBoundingClientRect();
                                const next = pairs[i+1]?.querySelector('.before-bar') ?? axis;
                                return {text: delta.textContent, visible: getComputedStyle(delta).visibility,
                                    left: box.left - value.left, gap: box.top - value.bottom,
                                    clearance: next.getBoundingClientRect().top - box.bottom};
                            });
                        }""", scale)
                        for row, reading in zip(rows, readings):
                            change = row["after"] - row["before"]
                            signed = f"{change:+d}".replace("-", "−") if change else "0"
                            self.assertEqual(reading["text"], f"{signed} días")
                            self.assertEqual(reading["visible"], "visible")
                            self.assertAlmostEqual(reading["left"], 0, delta=1)
                            self.assertGreaterEqual(reading["gap"], 0)
                            self.assertLess(reading["gap"], 25)
                            self.assertGreaterEqual(reading["clearance"], 0)


if __name__ == "__main__":
    unittest.main()
