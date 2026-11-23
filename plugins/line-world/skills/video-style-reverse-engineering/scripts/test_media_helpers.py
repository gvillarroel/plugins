#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=10.1,<13", "playwright>=1.49,<2"]
# ///
"""Exercise media evidence, exact render contracts and failure preservation."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from playwright.sync_api import Error as PlaywrightError, sync_playwright


def load(name: str):
    path = Path(__file__).resolve().parent / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inspector, renderer = load("inspect_video"), load("render_html")


def ffmpeg(*arguments: str) -> None:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", *arguments], check=True, capture_output=True)


class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            raise unittest.SkipTest("FFmpeg and ffprobe are required.")
        cls.temporary = tempfile.TemporaryDirectory(prefix="media-helper-test-", dir=Path.cwd())
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "reference with spaces.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=64x96:rate=10", "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-y", str(cls.source))
        cls.audio = cls.root / "short audio.wav"
        ffmpeg("-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "0.25", "-y", str(cls.audio))
        cls.html = cls.root / "source with spaces.html"
        cls.html.write_text("""<!doctype html><html><style>html,body {margin:0;width:100%;height:100%;overflow:hidden}</style>
            <script>window.renderAt=t=>document.body.style.background=t<0.5?'rgb(240,20,20)':'rgb(20,20,240)';</script></html>""", encoding="utf-8")
        with sync_playwright() as playwright:
            try:
                browser = renderer.launch_browser(playwright)
                browser.close()
                cls.browser_available = True
            except PlaywrightError:
                cls.browser_available = False

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_decoded_timestamp_manifest_sheet_and_hash(self):
        output = self.root / "analysis with spaces"
        manifest = inspector.inspect(self.source, output, 3)
        self.assertEqual([f["timestamp_seconds"] for f in manifest["frames"]], [0.0, 1.0, 1.9])
        self.assertAlmostEqual(manifest["duration_seconds"], 2)
        self.assertEqual((manifest["width"], manifest["height"]), (64, 96))
        self.assertFalse(manifest["has_audio"])
        self.assertEqual(manifest["source_sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(json.loads((output / "manifest.json").read_text()), manifest)
        for frame in manifest["frames"]:
            self.assertTrue((output / frame["path"]).is_file())
            self.assertLess(frame["timestamp_seconds"], manifest["duration_seconds"])
        with Image.open(output / "contact-sheet.jpg") as sheet:
            self.assertEqual(sheet.size, (792, 336))
            self.assertGreater(len(sheet.getcolors(maxcolors=1000000)), 100)

    def test_inspection_missing_audio_only_and_bad_samples(self):
        for source, samples, expected in [
            (self.root / "missing.mp4", 3, "does not exist"),
            (self.audio, 3, "no video"),
            (self.source, 0, "between 1 and 60"),
        ]:
            with self.subTest(source=source, samples=samples), self.assertRaisesRegex(ValueError, expected):
                inspector.inspect(source, self.root / "invalid-analysis", samples)

    def test_single_sample_records_start(self):
        manifest = inspector.inspect(self.source, self.root / "single-analysis", 1)
        self.assertEqual(manifest["frames"][0]["timestamp_seconds"], 0)
        self.assertEqual(len(manifest["frames"]), 1)

    def test_nonzero_stream_start_is_normalized(self):
        offset = self.root / "offset source.mp4"
        ffmpeg("-i", str(self.source), "-c", "copy", "-output_ts_offset", "5", "-y", str(offset))
        manifest = inspector.inspect(offset, self.root / "offset-analysis", 3)
        self.assertEqual([f["timestamp_seconds"] for f in manifest["frames"]], [0.0, 1.0, 1.9])

    def test_vfr_sampling_uses_decoded_end_frame(self):
        source = self.root / "variable frame rate.mp4"
        ffmpeg("-f", "lavfi", "-i", "testsrc2=size=64x96:rate=10", "-frames:v", "7", "-vf", "select='lt(n,5)+eq(n,10)+eq(n,19)'", "-fps_mode", "vfr", "-c:v", "libx264", "-y", str(source))
        manifest = inspector.inspect(source, self.root / "vfr-analysis", 4)
        self.assertAlmostEqual(manifest["last_frame_timestamp_seconds"], 1.9)
        self.assertAlmostEqual(manifest["frames"][-1]["timestamp_seconds"], 1.9)
        # A failed seek on a long or incorrectly reported stream must retry the real presentation clock.
        read_bounds = inspector.read_frame_bounds
        attempts = []
        def empty_seek(path, start, fps, seek=None):
            attempts.append(seek)
            return None if seek is not None else read_bounds(path, start, fps)
        with patch.object(inspector, "read_frame_bounds", side_effect=empty_seek):
            last, end = inspector.frame_bounds(source, 0, 10, 10)
        self.assertEqual(attempts, [7, None])
        self.assertAlmostEqual(last, 1.9)
        self.assertAlmostEqual(end, 2)
        self.assertEqual(len(manifest["frames"]), 4)

    def test_render_rejects_invalid_contracts_before_browser(self):
        for width, fps, duration, expected in [(63, 4, 1, "even integers"), (64, 0, 1, "FPS"), (64, 4, .3, "whole frame"), (64, 60, 1000, "18000")]:
            with self.subTest(width=width, fps=fps, duration=duration), self.assertRaisesRegex(ValueError, expected):
                renderer.render(self.html, self.root / "invalid.mp4", width, 96, fps, duration)
        self.assertFalse((self.root / "invalid.mp4").exists())

    def require_browser(self):
        if not self.browser_available:
            self.skipTest("Chromium unavailable; install with uv run --with playwright python -m playwright install chromium")

    def test_render_dimensions_timing_and_actual_motion(self):
        self.require_browser()
        output = self.root / "silent render.mp4"
        result = renderer.render(self.html, output, 64, 96, 4, 1)
        self.assertEqual((result["width"], result["height"], result["frame_count"], result["fps"]), (64, 96, 4, 4))
        self.assertAlmostEqual(result["duration_seconds"], 1)
        self.assertFalse(result["has_audio"])
        for timestamp, channel in [(0, 0), (.75, 2)]:
            png = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(timestamp), "-i", str(output), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], check=True, capture_output=True).stdout
            with Image.open(io.BytesIO(png)) as image:
                pixel = image.convert("RGB").getpixel((32, 48))
                self.assertGreater(pixel[channel], 200)
                self.assertLess(pixel[1], 50)

    def test_audio_is_padded_to_video_duration(self):
        self.require_browser()
        output = self.root / "audio render.mp4"
        result = renderer.render(self.html, output, 64, 96, 4, 1, self.audio)
        metadata = json.loads(renderer.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]).stdout)
        audio = next(s for s in metadata["streams"] if s["codec_type"] == "audio")
        self.assertTrue(result["has_audio"])
        self.assertAlmostEqual(float(audio["duration"]), 1, delta=.03)

    def test_failed_render_preserves_existing_output(self):
        self.require_browser()
        broken = self.root / "no-render-function.html"
        broken.write_text("<!doctype html><p>Static HTML</p>", encoding="utf-8")
        output = self.root / "preserved.mp4"
        output.write_bytes(b"existing-output")
        with self.assertRaisesRegex(ValueError, "must expose"):
            renderer.render(broken, output, 64, 96, 4, 1)
        self.assertEqual(output.read_bytes(), b"existing-output")
        self.assertEqual(list(self.root.glob("html-render-*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
