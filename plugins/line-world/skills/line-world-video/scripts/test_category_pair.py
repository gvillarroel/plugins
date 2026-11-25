#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Verify the two-category reading at delivery size in Chromium."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

from inspect_focus import browser_path
from line_world import build


class CategoryPairTest(unittest.TestCase):
    def test_category_shares_and_text_at_delivery_size(self):
        with tempfile.TemporaryDirectory() as temp, sync_playwright() as playwright:
            project = Path(temp) / "film"
            subprocess.run([sys.executable, str(Path(__file__).with_name("line_world.py")),
                            "init", "--project", str(project)], capture_output=True, check=True)
            story_path = project / "story.json"
            story = json.loads(story_path.read_text(encoding="utf-8"))
            theme_path = project / "theme.json"
            theme = json.loads(theme_path.read_text(encoding="utf-8"))
            original_rows = story["rows"]
            story["unit"] = "días"
            story["copy"].update(after="Después", synthetic="datos sintéticos")
            browser = playwright.chromium.launch(executable_path=browser_path(), headless=True)
            page = browser.new_page(viewport={"width": 960, "height": 540})
            for values in ((12, 8), (99, 1), (1, 99), (12, 0), (12, 8, 16, 6)):
                with self.subTest(values=values):
                    story["rows"] = [dict(row, after=value) for row, value in zip(original_rows, values)]
                    story["rows"][1]["label"] = "Revisión técnica final"
                    theme["fontScale"] = 1.5 if 99 in values else 1
                    if 99 in values:
                        story["rows"][0]["label"] = "W" * 22
                    theme_path.write_text(json.dumps(theme), encoding="utf-8")
                    story_path.write_text(json.dumps(story, ensure_ascii=False), encoding="utf-8")
                    build(project)
                    page.goto((project / "index.html").as_uri())
                    page.evaluate("() => window.ready")
                    state = page.evaluate("""() => {
                        const beat = STORY.beats.find(b => b.id === 'categories');
                        renderAt(beat.end - .125);
                        const cell = [...document.querySelectorAll('#categories .cell')];
                        const rects = cell.map(group => group.querySelector('rect'));
                        const nums = cell.map(group => group.querySelector('.world-number'));
                        const texts = [...document.querySelectorAll('#categories text')];
                        const bounds = texts.map(t => t.getBoundingClientRect());
                        const overlaps = bounds.some((a,i) => bounds.slice(i+1).some(b =>
                            a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top));
                        const guide = document.querySelector('#attention-dot circle').getBoundingClientRect();
                        return {shares: rects.filter(r => r.dataset.encoding === 'quantity').map(r =>
                                    r.getBoundingClientRect().width),
                                lastFill: getComputedStyle(rects.at(-1)).fill,
                                selectedFill: getComputedStyle(nums.at(-1)).fill,
                                names: cell.map(g => g.querySelector('.world-label').textContent),
                                values: nums.map(n => +n.textContent),
                                legends: texts.filter(t => t.textContent === 'Después · días · datos sintéticos').length,
                                overlaps, guideGap: guide.left - nums.at(-1).getBoundingClientRect().right,
                                inside: bounds.every(b => b.left >= 0 && b.right <= innerWidth &&
                                                         b.top >= 0 && b.bottom <= innerHeight)};
                    }""")
                    self.assertEqual(state["values"], [v for v in values if v > 0])
                    if len(values) != 2 or 0 in values:
                        self.assertFalse(state["shares"])
                        continue
                    self.assertEqual(state["names"][1], "Revisión técnica final")
                    self.assertEqual(len(state["shares"]), 2)
                    self.assertAlmostEqual(state["shares"][0] / sum(state["shares"]),
                                           values[0] / sum(values), places=4)
                    self.assertEqual(state["lastFill"], state["selectedFill"])
                    self.assertEqual(state["legends"], 1)
                    self.assertFalse(state["overlaps"])
                    self.assertTrue(state["inside"])
                    self.assertGreater(state["guideGap"], 2)


if __name__ == "__main__":
    unittest.main()
