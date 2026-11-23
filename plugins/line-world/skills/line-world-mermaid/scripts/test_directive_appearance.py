# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13", "playwright==1.58.0"]
# ///
"""Exercise authored mark, paint and movement at intermediate browser timestamps."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from playwright.sync_api import sync_playwright

from audit_animation_modes import capture, load_svg
from test_animation_modes import FIXTURE, HERE


class DirectiveAppearance(unittest.TestCase):
    def test_solid_and_native_directives_share_cues_and_differ_in_paint(self):
        with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
            work = Path(tmp)
            source = work / "diagram.svg"
            source.write_text(FIXTURE, encoding="utf-8")
            cues = work / "cues.mmd"
            cues.write_text(
                """%% @animate v1
%% @animate target item = css:#flowchart-A-0
%% @animate mark dot at xy(45,32) shape=dot size=8 fill=#9e1b32
%% @animate at 0s move dot to=xy(90,32) duration=480ms
%% @animate at 480ms color item fill=#000000 duration=480ms
%% @animate at 960ms pulse item scale=1.04 duration=320ms
%% @animate at 1280ms hide dot duration=320ms
""",
                encoding="utf-8",
            )
            browser = pw.chromium.launch(
                channel="msedge" if sys.platform == "win32" else None
            )
            page = browser.new_page(viewport={"width": 512, "height": 288})
            partial = {}
            for mode in ("solid", "native"):
                output = work / (mode + ".svg")
                receipt = work / (mode + ".json")
                completed = subprocess.run(
                    [
                        sys.executable,
                        str(HERE / "animate_mermaid_svg.py"),
                        "--svg-input",
                        str(source),
                        "-o",
                        str(output),
                        "--directives-file",
                        str(cues),
                        "--appearance",
                        mode,
                        "--animation-report",
                        str(receipt),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                load_svg(page, output)
                samples = [
                    capture(page, ms)
                    for ms in (0, 20, 160, 470, 650, 800, 960, 1100, 1310, 1440, 1610)
                ]
                partial[mode] = max(state["partial"] for _, state in samples)
                self.assertNotEqual(samples[2][0].tobytes(), samples[-1][0].tobytes())
                report = json.loads(receipt.read_text())
                self.assertEqual(
                    (
                        report["directive_actions"],
                        report["animated"],
                        report["duration_ms"],
                    ),
                    (4, 2, 1600),
                )
            self.assertEqual(partial["solid"], 0)
            self.assertGreater(partial["native"], 0)
            browser.close()


if __name__ == "__main__":
    unittest.main()
