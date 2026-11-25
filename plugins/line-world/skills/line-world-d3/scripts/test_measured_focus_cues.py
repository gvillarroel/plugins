#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Bind and inspect measured comparison emphasis across forward and backward seeks."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from playwright.sync_api import sync_playwright
import video_chart

sys.path.insert(0, str(video_chart.SKILL.parent / "reference-motion/scripts"))
from adapt_motion import adapt


def request(encoding):
    narration = {"duration_s": 4, "words":[{"text":"North","start_s":1}],
                 "cues":[{"target":"North","word_index":0,"offset_s":-.25,"hold_s":.5,"role":"emphasis"},
                         {"target":"r2","mention_s":2,"hold_s":1,"role":"emphasis"}]}
    if encoding == "paired-change":
        return {"narration":narration,"intent":encoding,"unit":"m",
                "rows":[{"item":"North","before":3,"after":6},{"item":"South","before":2,"after":1}]}
    return {"narration":narration,"rows":[{"category":"North","numerator":3,"denominator":8},
                                          {"category":"South","numerator":1,"denominator":10}]}


class MeasuredFocusCuesTest(unittest.TestCase):
    def test_roles_targets_and_overlapping_times_keep_specialist_handoff(self):
        for change in ({"role":"result"}, {"target":"Unknown"}, {"pose":.5},
                       {"hold_s":2}, {"hold_s":.005}, {"hold_s":8}):
            with self.subTest(change=change):
                req = request("rate-comparison")
                req["narration"]["cues"][0].update(change)
                _, report = adapt(req)
                self.assertEqual(report["narration"]["status"], "handoff")
                self.assertNotIn("focusCues", report["d3_chart"])

    def test_exact_cue_windows_control_geometry_for_both_encodings(self):
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(executable_path=video_chart.browser_path())
            for encoding in ("rate-comparison", "paired-change"):
                with self.subTest(encoding=encoding), TemporaryDirectory() as directory:
                    _, report = adapt(request(encoding))
                    self.assertEqual(report["narration"]["status"], "bound")
                    self.assertEqual([c["frame"] for c in report["narration"]["cues"]], [18,48])
                    data = video_chart.check_data(report["d3_chart"])
                    self.assertEqual(data["duration"], 4)
                    project = Path(directory)
                    video_chart.build_project(project, data)
                    page = browser.new_page(viewport={"width":960,"height":540})
                    page.goto((project / "scene.html").as_uri())
                    page.evaluate("document.fonts.ready")
                    for t, target in [(0,None),(.749,None),(.75,"r1"),(1.24,"r1"),(1.25,None),
                                      (2,"r2"),(3,None),(.92,"r1"),(0,None)]:
                        state = page.evaluate("t=>renderAt(t)", t)
                        self.assertEqual(state["selectedId"], target)
                        self.assertEqual(page.locator('[data-motion-track="end-marker"]:visible').count(), 1 if target else 0)
                    motion = page.evaluate((video_chart.SKILL / "scripts/video_chart_motion_audit.js").read_text(), 4)
                    self.assertTrue(motion["ok"], motion["issues"])
                    page.close()
            browser.close()


if __name__ == "__main__":
    unittest.main()
