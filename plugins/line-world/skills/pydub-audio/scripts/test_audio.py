#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydub==0.25.1", "audioop-lts==0.2.2; python_version >= '3.13'"]
# ///
"""Exercise real PCM/codec outputs, timing and non-overwriting boundaries."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import audio


class AudioTests(unittest.TestCase):
    def setUp(self):
        # Caller controls scratch placement; installed bundle stays read-only.
        self.temp = tempfile.TemporaryDirectory(prefix="pydub-audio-", dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def render(self, plan, name="mix.wav"):
        (self.root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        return audio.render(self.root, "plan.json", name, name + ".json")

    @staticmethod
    def tone(id="a", duration=1000, **extra):
        return {"id": id, "tone": {"kind": "sine", "frequency_hz": 440, "duration_ms": duration}, **extra}

    def test_sequence_trim_crossfade_and_encoded_receipt(self):
        result = self.render({"schema_version": 1, "sample_rate": 16000, "channels": 1,
                              "clips": [self.tone(start_ms=100, end_ms=900), self.tone("b", crossfade_ms=200)]})
        self.assertEqual(result["duration_ms"], 1600)
        self.assertEqual(result["sample_rate"], 16000)
        self.assertEqual(result["channels"], 1)
        self.assertEqual(result["sha256"], audio.sha(self.root / "mix.wav"))
        self.assertEqual(audio.inspect(self.root, "mix.wav")["duration_ms"], 1600)

    def test_timeline_extends_canvas_and_ducks_existing_bed(self):
        plan = {"schema_version": 1, "mode": "timeline", "channels": 1,
                "clips": [self.tone(duration=2000), {"id": "quiet", "silence_ms": 1000, "position_ms": 500, "duck_db": -12}]}
        self.render(plan)
        decoded = audio.load_audio(self.root / "mix.wav")
        self.assertEqual(len(decoded), 2000)
        self.assertAlmostEqual(decoded[600:1400].dBFS - decoded[0:400].dBFS, -12, delta=0.1)
        plan["clips"].append(self.tone("tail", position_ms=2500))
        self.assertEqual(self.render(plan, "extended.wav")["duration_ms"], 3500)

    def test_silence_has_json_null_levels(self):
        result = self.render({"schema_version": 1, "peak_dbfs": -1, "clips": [{"id": "silent", "silence_ms": 500}]})
        self.assertIsNone(result["rms_dbfs"])
        self.assertIsNone(result["sample_peak_dbfs"])
        self.assertEqual(audio.inspect(self.root, "mix.wav", -40)["silence_ranges_ms"], [[0, 500]])

    def test_outputs_and_sources_are_preserved(self):
        self.render({"schema_version": 1, "clips": [self.tone()]})
        before = (self.root / "mix.wav").read_bytes()
        with self.assertRaises(ValueError):
            self.render({"schema_version": 1, "clips": [self.tone(duration=500)]})
        self.assertEqual((self.root / "mix.wav").read_bytes(), before)
        self.assertFalse((self.root / ".outside.wav").exists())
        with self.assertRaises(ValueError):
            audio.render(self.root, "plan.json", "../escape.wav", "safe.json")

    def test_bad_plan_publishes_nothing(self):
        for clip in [self.tone(end_ms=1500), self.tone(start_ms=-1), self.tone(crossfade_ms=10),
                     self.tone(unrecognized=True), self.tone(gain_db=float("nan")), self.tone(reverse="yes")]:
            with self.subTest(clip=clip), self.assertRaises(ValueError):
                self.render({"schema_version": 1, "clips": [clip]})
            self.assertFalse((self.root / "mix.wav").exists())
            self.assertFalse((self.root / "mix.wav.json").exists())

    def test_source_paths_are_workspace_relative_and_hashed(self):
        self.render({"schema_version": 1, "clips": [self.tone()]}, "source.wav")
        result = self.render({"schema_version": 1, "clips": [{"id": "file", "file": "source.wav", "start_ms": 100, "end_ms": 400}]})
        self.assertEqual(result["sources"][0]["sha256"], audio.sha(self.root / "source.wav"))
        self.assertEqual(result["duration_ms"], 300)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg is unavailable")
    def test_compressed_exports_decode_and_probe(self):
        for suffix in ("mp3", "ogg", "flac", "m4a"):
            result = self.render({"schema_version": 1, "sample_rate": 48000, "clips": [self.tone()], "bitrate": "128k"}, "delivery." + suffix)
            self.assertAlmostEqual(result["duration_ms"], 1000, delta=80)
            self.assertEqual(audio.inspect(self.root, "delivery." + suffix)["channels"], 2)


if __name__ == "__main__":
    unittest.main()
