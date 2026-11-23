"""Regression checks for scripted solid appearances and static diagram handoff."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace

from mermaid_animation.solid_motion import arrange, solid_source_paints
from video_style import native_video_presentation

HERE = Path(__file__).resolve().parent
FIXTURE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60"
 aria-roledescription="flowchart" data-colorset="colorset1">
 <g class="nodes"><g id="flowchart-A-0" class="node"><rect width="45" height="30" fill="#9e1b32"/>
 <text x="10" y="15" fill="#ffffff">A</text></g></g>
 <line x1="45" x2="80" y1="10" y2="10" class="flowchart-link" stroke="#000000" stroke-dasharray="4 3"/>
</svg>"""


class AnimationModes(unittest.TestCase):
    def test_mindmap_connectors_remain_stroked(self):
        root = ET.fromstring(
            '<svg><path class="edge section-edge-3" d="M10 10 L100 30"/></svg>'
        )
        native_video_presentation(root, "colorset1")
        edge = root[0]
        self.assertIn("stroke:#333e48!important", edge.get("style"))
        self.assertIn("fill:none!important", edge.get("style"))
        self.assertIsNone(edge.get("data-lw-surface"))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / "source.svg"
        self.source.write_text(FIXTURE, encoding="utf-8")
        self.svg = self.folder / "result.svg"
        self.report = self.folder / "plan.json"

    def execute(self, *extra, success=True):
        result = subprocess.run(
            [
                sys.executable,
                str(HERE / "animate_mermaid_svg.py"),
                "--svg-input",
                str(self.source),
                "-o",
                str(self.svg),
                "--animation-report",
                str(self.report),
                *extra,
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode == 0, success, result.stderr)
        return result.stderr

    def test_none_ignores_sidecar_and_records_zero(self):
        sidecar = self.folder / "timing.mmd"
        sidecar.write_text(
            "%% @animate v1\n%% @animate target first = css:#flowchart-A-0\n"
            "%% @animate at 0s reveal first duration=1s",
            encoding="utf-8",
        )
        self.execute("--directives-file", str(sidecar), "--animation", "none")
        report = json.loads(self.report.read_text())
        self.assertGreater(report["detected"], 0)
        self.assertEqual(
            (report["animated"], report["duration_ms"], report["effects"]), (0, 0, {})
        )
        self.assertNotIn("am-step", self.svg.read_text(encoding="utf-8"))
        self.execute("--directives-file", str(sidecar))
        self.assertEqual(json.loads(self.report.read_text())["effective"], "directives")

    def test_native_is_explicit_and_solid_draw_preserves_native_dashes(self):
        self.execute("--animation", "draw")
        root = ET.parse(self.svg).getroot()
        line = root.find(".//{*}line")
        self.assertIsNone(line.get("pathLength"))
        self.assertEqual(line.get("stroke-dasharray"), "4 3")
        self.assertEqual(root.get("data-animation-appearance"), "solid")
        self.execute("--animation", "fade", "--appearance", "native")
        self.assertIn("@keyframes am-fade", self.svg.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(self.report.read_text())["appearance"], "native")

    def test_custom_solid_color_rejects_fractional_opacity(self):
        sidecar = self.folder / "color.mmd"
        sidecar.write_text(
            "%% @animate target a = css:#flowchart-A-0\n"
            "%% @animate at 0s color a opacity=.5 duration=1s",
            encoding="utf-8",
        )
        self.assertIn(
            "opacity 0 or 1",
            self.execute("--directives-file", str(sidecar), success=False),
        )
        self.execute("--directives-file", str(sidecar), "--appearance", "native")

    def test_source_paints_keep_invisible_content_and_opaque_ink(self):
        root = ET.fromstring(
            "<svg><style>.a{opacity:0.5;fill:rgba(0,0,0,.3)}</style>"
            '<g opacity="0"><rect style="fill:#9e1b3280;fill-opacity:48%"/></g></svg>'
        )
        solid_source_paints(root)
        self.assertEqual(root[0].text, ".a{opacity:1;fill:rgb(0,0,0)}")
        self.assertEqual(root[1].get("opacity"), "0")
        self.assertEqual(root[1][0].get("style"), "fill:#9e1b32;fill-opacity:1")

    def test_simultaneous_endings_preserve_order_and_run_length(self):
        candidates = [
            SimpleNamespace(delay_ms=0, effect="draw", duration_ms=200)
            for _ in range(13)
        ]
        self.assertEqual(arrange(candidates, 3), 3)
        self.assertEqual(
            [c.delay_ms for c in candidates],
            [0] * 3 + [200] * 3 + [400] * 3 + [600] * 3 + [800],
        )
        self.assertEqual(arrange(candidates), 3)
        self.assertTrue(all(c.duration_ms == 200 for c in candidates))

    def test_report_cannot_overwrite_input(self):
        msg = self.execute("--animation-report", str(self.source), success=False)
        self.assertIn("separate file", msg)
        self.assertEqual(self.source.read_text(), FIXTURE)


if __name__ == "__main__":
    unittest.main()
