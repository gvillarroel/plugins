#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10.0.0"]
# ///
"""Exercise the delivery commands against real MP4 stream durations."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from video_probe import video_duration


SCRIPT_DIR = Path(__file__).resolve().parent


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg and FFprobe are required")
class VideoDeliveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace = tempfile.TemporaryDirectory()
        cls.addClassCleanup(workspace.cleanup)
        cls.root = Path(workspace.name)
        cls.control = cls.root / "control.mp4"
        cls.picture_cut = cls.root / "picture-cut.mp4"
        cls.audio_only = cls.root / "audio-only.mp4"
        cls.audio_cover = cls.root / "audio-cover.mp4"
        cls.video_cover = cls.root / "video-cover.mp4"
        cls.matroska_control = cls.root / "control.mkv"
        cls.matroska_cut = cls.root / "picture-cut.mkv"
        cover = cls.root / "cover.jpg"
        cls.ffmpeg(
            "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=4",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
            "-c:v", "mpeg4", "-c:a", "aac", str(cls.control),
        )
        cls.ffmpeg(
            "-i", str(cls.control), "-vf", "trim=duration=2",
            "-c:v", "mpeg4", "-c:a", "copy", str(cls.picture_cut),
        )
        cls.ffmpeg("-i", str(cls.control), "-vn", "-c:a", "copy", str(cls.audio_only))
        cls.ffmpeg("-i", str(cls.control), "-c", "copy", str(cls.matroska_control))
        cls.ffmpeg("-i", str(cls.picture_cut), "-c", "copy", str(cls.matroska_cut))
        cls.ffmpeg("-i", str(cls.control), "-vf", "scale=640:360", "-frames:v", "1", str(cover))
        cls.ffmpeg(
            "-i", str(cls.audio_only), "-i", str(cover), "-map", "0:a", "-map", "1:v",
            "-c", "copy", "-disposition:v", "attached_pic", str(cls.audio_cover),
        )
        cls.ffmpeg(
            "-i", str(cls.control), "-i", str(cover), "-map", "0", "-map", "1:v",
            "-c", "copy", "-disposition:v:1", "attached_pic", str(cls.video_cover),
        )

    @staticmethod
    def ffmpeg(*args):
        subprocess.run(["ffmpeg", "-v", "error", *args], check=True)

    def check(self, validator, video, expected_duration):
        report = self.root / f"{validator}.json"
        duration = ["--expect-duration", str(expected_duration)]
        commands = {
            "outputs": ["check_video_outputs.py", str(video), *duration],
            "artifact": ["check_video_artifact.py", str(video), *duration, "--min-size-bytes", "1", "--require-audio", "--json"],
            "quality": ["review_video_quality.py", "--video", str(video), *duration, "--report", str(report)],
        }
        script, *args = commands[validator]
        result = subprocess.run([sys.executable, str(SCRIPT_DIR / script), *args], capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        source = report.read_text(encoding="utf-8") if validator == "quality" else result.stdout
        return result.returncode, json.loads(source)

    def test_matching_picture_and_audio_pass(self):
        for validator in ("outputs", "artifact", "quality"):
            with self.subTest(validator=validator):
                status, report = self.check(validator, self.control, 4)
                self.assertEqual(status, 0, report)

    def test_video_with_cover_art_uses_the_playable_picture(self):
        for validator in ("outputs", "artifact", "quality"):
            with self.subTest(validator=validator):
                status, report = self.check(validator, self.video_cover, 4)
                self.assertEqual(status, 0, report)
                if validator == "artifact":
                    self.assertEqual(report["streams"]["video"], 1)
                    width = report["properties"]["width"]
                elif validator == "outputs":
                    width = report["media"]["actual"]["width"]
                else:
                    width = report["video"]["width"]
                self.assertEqual(width, 320)

    def test_audio_cannot_mask_the_short_picture(self):
        for validator in ("outputs", "artifact", "quality"):
            with self.subTest(validator=validator):
                status, report = self.check(validator, self.picture_cut, 4)
                self.assertEqual(status, 1, report)
                if validator == "artifact":
                    self.assertIn("expected video duration 4.0s, got 2.000s", report["failures"])
                else:
                    code = "duration-mismatch" if validator == "outputs" else "duration"
                    self.assertIn(code, [item["code"] for item in report["findings"]])

    def test_file_duration_constraint_still_applies(self):
        for validator in ("outputs", "artifact", "quality"):
            with self.subTest(validator=validator):
                status, report = self.check(validator, self.picture_cut, 2)
                self.assertEqual(status, 1, report)
                if validator == "artifact":
                    self.assertIn("expected container duration 2.0s, got 4.000s", report["failures"])
                else:
                    code = "container-duration-mismatch" if validator == "outputs" else "container-duration"
                    self.assertIn(code, [item["code"] for item in report["findings"]])

    def test_matroska_durations_remain_track_specific(self):
        for validator in ("outputs", "artifact", "quality"):
            with self.subTest(validator=validator):
                status, report = self.check(validator, self.matroska_control, 4)
                self.assertEqual(status, 0, report)
                status, report = self.check(validator, self.matroska_cut, 4)
                self.assertEqual(status, 1, report)

    def test_audio_only_file_has_a_missing_video_finding(self):
        for video in (self.audio_only, self.audio_cover):
            for validator in ("outputs", "artifact", "quality"):
                with self.subTest(validator=validator, video=video.name):
                    status, report = self.check(validator, video, 4)
                    self.assertEqual(status, 1, report)
                    if validator == "artifact":
                        self.assertIn("no video stream found", report["failures"])
                    else:
                        self.assertIn("missing-video-stream", [item["code"] for item in report["findings"]])


class VideoDurationTest(unittest.TestCase):
    def test_track_end_timestamp_accounts_for_stream_start(self):
        stream = {"start_time": "1.500", "tags": {"DURATION": "00:00:05.500000000"}}
        self.assertEqual(video_duration(stream), 4.0)

    def test_track_duration_requires_usable_metadata(self):
        self.assertIsNone(video_duration({"start_time": "0.000"}))
        self.assertIsNone(video_duration({"tags": {"DURATION": "00:00:05.500000000"}}))


if __name__ == "__main__":
    unittest.main()
