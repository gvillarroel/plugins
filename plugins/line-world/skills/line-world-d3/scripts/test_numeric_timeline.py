#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Numeric time-axis contract, geometry and seek regressions."""
from copy import deepcopy
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from playwright.sync_api import sync_playwright

import video_chart

sys.path.insert(0, str(video_chart.SKILL.parent / "reference-motion/scripts"))
from adapt_motion import columns_for, dated_chart


def chart():
    return {"kind": "time-series", "unit": "kW", "timeUnit": "min", "revealObservations": True,
            "observations": [{"t": t, "value": v} for t, v in [(0, 8), (1.5, 3), (6, None), (10, 7)]]}


class NumericTimelineTest(unittest.TestCase):
    def test_adapter_preserves_day_numbers_units_and_null(self):
        rows = [{"día": t, "lectura": value} for t, value in [(24, 5), (3, 8), (17, None), (10, 7)]]
        fields = columns_for(rows, {})
        spec = dated_chart(rows, fields, {"timeUnit": "día del mes", "unit": "cm"})
        self.assertEqual(spec["observations"], [{"t": 3, "value": 8}, {"t": 10, "value": 7},
                                              {"t": 17, "value": None}, {"t": 24, "value": 5}])
        self.assertEqual(video_chart.check_data(spec)["timeUnit"], "día del mes")
        for row in rows:
            row["time_unit"] = "día del mes"
        fields = columns_for(rows, {"value":"lectura"})
        self.assertEqual(dated_chart(rows, fields, {"unit": "cm"})["timeUnit"], "día del mes")
        with self.assertRaises(ValueError):
            dated_chart(rows, fields, {"unit": "cm", "timeUnit": "min"})

    def test_rejects_missing_units_mixed_coordinates_and_invalid_time(self):
        missing_unit = chart()
        del missing_unit["timeUnit"]
        mixed = chart()
        mixed["observations"][0]["date"] = "2025-01-01"
        for invalid in [None, True, 0, "2", float("inf"), float("nan"), -3]:
            data = chart()
            data["observations"][1]["t"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                video_chart.check_data(data)
        for data in [missing_unit, mixed]:
            with self.assertRaises(ValueError):
                video_chart.check_data(data)

    def test_rendered_elapsed_minutes_reveal_and_reverse_seek(self):
        data = video_chart.check_data(deepcopy(chart()))
        with TemporaryDirectory() as folder, sync_playwright() as pw:
            project = Path(folder)
            video_chart.build_project(project, data)
            browser = pw.chromium.launch(executable_path=video_chart.browser_path())
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.goto((project / "scene.html").as_uri())
            page.evaluate("document.fonts.ready")
            page.evaluate("new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
            def visible_times():
                return sorted(map(float, page.locator("#timeline [data-t]:visible").evaluate_all(
                    "nodes=>nodes.map(n=>n.dataset.t)")))
            self.assertEqual(visible_times(), [0])
            self.assertIsNone(page.evaluate("renderAt(3.7).value"))
            self.assertEqual(visible_times(), [0, 1.5, 6])
            self.assertEqual(page.locator(".last-date").text_content(), "min · 6")
            self.assertEqual(page.evaluate("renderAt(8).lastObservedTime"), 10)
            self.assertEqual(visible_times(), [0, 1.5, 6, 10])
            self.assertEqual(page.locator("#timeline [data-date]").count(), 0)
            self.assertEqual(page.locator(".trend").get_attribute("d").count("M"), 2)
            audit = page.evaluate((video_chart.SKILL / "scripts/video_chart_audit.js").read_text(encoding="utf-8"))
            self.assertTrue(audit["numericTimeSpacing"] and audit["timeUnitVisible"])
            self.assertEqual(audit["values"], [8, 3, None, 7])
            self.assertFalse(audit["overlaps"] or audit["outside"])
            page.evaluate("renderAt(0)")
            self.assertEqual(visible_times(), [0])
            browser.close()


if __name__ == "__main__":
    unittest.main()
