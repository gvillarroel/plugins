"""Check the director's data-to-motion handoff and all-or-nothing publication."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import line_world


class BriefPublication(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "film"
        self.project.mkdir()
        self.request = self.root / "solicitud.json"
        self.request.write_text('{"brief":"seguir un recorrido"}', encoding="utf-8")
        skill = self.root / "skills" / "line-world-video"
        sibling = skill.parent / "reference-motion" / "scripts"
        sibling.mkdir(parents=True)
        (sibling / "adapt_motion.py").touch()
        mock_skill = patch.object(line_world, "SKILL", skill)
        mock_skill.start()
        self.addCleanup(mock_skill.stop)

    def invoke(self, status, failed_render=False, dated_series=None):
        def producer(command, cwd, **_):
            if "--out" in command:
                report = {"status": status, "producer": "reference-motion" if status == "recipe" else "line-world-d3"}
                if dated_series:
                    report["d3_chart"] = dated_series
                (cwd / "direction.json").write_text(json.dumps(report), encoding="utf-8")
                if status == "recipe":
                    (cwd / "scene.json").write_text("{}", encoding="utf-8")
            elif "build" in command:
                actual = json.loads((cwd / "chart-input.json").read_text(encoding="utf-8"))
                self.assertEqual(actual, {**dated_series, "revealObservations": True})
                for name in ("data.json", "scene.html", "d3.min.js", "D3-LICENSE.txt"):
                    (cwd / name).touch()
            elif "export" in command:
                for name in ("scene.svg", "scene.png", "scene.mp4", "scene.qa.json"):
                    (cwd / name).touch()
            elif failed_render:
                (cwd / "scene.mp4").write_bytes(b"incomplete")
                return subprocess.CompletedProcess(command, 1, b"", "error de composición".encode("utf-8"))
            else:
                self.assertEqual(command[-5:], ["render", "scene.json", "scene.mp4", "--report", "scene.qa.json"])
                (cwd / "scene.mp4").write_bytes(b"verified by producer")
                (cwd / "scene.qa.json").write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, b"", b"")
        with patch.object(subprocess, "run", side_effect=producer) as runner:
            result = line_world.from_brief(self.request, self.project)
        return result, runner.call_count

    def test_referrals_publish_only_the_direction(self):
        for status in ("specialist", "static", "needs-input"):
            with self.subTest(status=status):
                result, calls = self.invoke(status)
                self.assertEqual((result["status"], calls), (status, 1))
                self.assertEqual([p.name for p in self.project.iterdir()], ["direction.json"])
                (self.project / "direction.json").unlink()

    def test_a_recipe_reaches_export_and_preserves_prior_deliveries(self):
        result, calls = self.invoke("recipe")
        self.assertEqual(calls, 2)
        self.assertEqual({Path(p).name for p in result["outputs"]},
                         {"direction.json", "scene.json", "scene.mp4", "scene.qa.json"})
        with self.assertRaisesRegex(ValueError, "unused scene paths"):
            self.invoke("recipe")
        self.assertEqual((self.project / "scene.mp4").read_bytes(), b"verified by producer")

    def test_failed_render_keeps_the_output_directory_clean(self):
        keep = self.project / "voice.wav"
        keep.write_bytes(b"recording")
        with self.assertRaisesRegex(ValueError, "composición"):
            self.invoke("recipe", failed_render=True)
        self.assertEqual(list(self.project.iterdir()), [keep])
        self.assertEqual(keep.read_bytes(), b"recording")

    def test_dated_series_handoff_calls_the_actual_producer_entry_points(self):
        chart = {"kind":"time-series","unit":"g/L","observations":[
            {"date":"2025-01-01","value":2.1},{"date":"2025-01-04","value":None}]}
        result, calls = self.invoke("specialist", dated_series=chart)
        self.assertEqual((result["producer"], calls), ("line-world-d3", 3))
        self.assertEqual(Path(result["movie"]).name, "scene.mp4")
        self.assertTrue((self.project / "data.json").exists())
        self.assertTrue((self.project / "D3-LICENSE.txt").exists())


if __name__ == "__main__":
    unittest.main()
