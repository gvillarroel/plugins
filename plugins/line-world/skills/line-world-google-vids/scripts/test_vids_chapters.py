#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Exercise a real inter-frame chapter cut, both audio routes and transcript gates."""
import copy
import math
import shutil
import subprocess
import tempfile
import unittest
from array import array
from pathlib import Path

import vids_batch
import vids_chapters
from vids_plan import read, write


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "Requires FFmpeg and FFprobe")
class ChapterImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        cls.root = Path(cls.tmp.name)
        cls.video = cls.root / "source.mp4"
        metadata = cls.root / "chapters.ffmeta"
        metadata.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/10\nSTART=0\nEND=7\ntitle=First\n"
                            "[CHAPTER]\nTIMEBASE=1/10\nSTART=7\nEND=20\ntitle=Second\n")
        subprocess.run([*vids_chapters.FFMPEG, "-f", "lavfi", "-i", "testsrc2=size=144x96:rate=10:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=431:sample_rate=48000:duration=2",
                        "-f", "ffmetadata", "-i", str(metadata), "-map", "0:v", "-map", "1:a", "-map_chapters", "2",
                        "-c:v", "libx264", "-g", "50", "-sc_threshold", "0", "-threads", "1", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(cls.video)], check=True, capture_output=True)
        cls.timeline = {"sample_rate": 48000, "scenes": [
            {"id": "uno", "start_sample": 0, "end_sample": 33600, "sentences": [
                {"text": "Una.", "absolute_start_sample": 2000, "absolute_end_sample": 20000}]},
            {"id": "dos", "start_sample": 33600, "end_sample": 96000, "sentences": [
                {"text": "Dos.", "absolute_start_sample": 40000, "absolute_end_sample": 60000},
                {"text": "Otra frase.", "absolute_start_sample": 70000, "absolute_end_sample": 92000}]}]}
        cls.clock = cls.root / "timeline.json"
        write(cls.clock, cls.timeline)
        cls.project = cls.root / "project.json"
        write(cls.project, {"audioTimeline": "timeline.json", "fps": 10, "width": 144, "height": 96,
                            "scenes": [{"id": "uno", "title": "First"}, {"id": "dos", "title": "Second"}]})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_native_clips_and_real_batch_entrypoint(self):
        dest = self.root / "native"
        receipt = vids_chapters.prepare(self.video, dest, project_file=self.project)
        self.assertEqual([s["frames"] for s in receipt["scenes"]], [7, 13])
        self.assertEqual([s["audioTracks"] for s in receipt["scenes"]], [0, 0])
        self.assertFalse(receipt["scenes"][1]["sourceStartsOnKeyframe"])
        self.assertEqual(receipt["sentenceCount"], 3)
        plan = read(dest / "handoff/insertion-plan.json")
        self.assertEqual(plan["scenes"][1]["script"], "Dos. Otra frase.")
        self.assertEqual(plan["scenes"][1]["clip"], "clips/dos.mp4")
        self.assertFalse(any(r["observed"] for r in read(dest / "handoff/observed.json")["scenes"]))
        self.assertEqual([t["kind"] for t in read(dest / "handoff/queue.json")["tasks"]],
                         ["verify-order", "voiceover", "voiceover"])
        measurement = self.root / "synthetic-observations.json"
        write(measurement, {"voice": "Fixture only", "scenes": [
            {"id": s["id"], "sceneSeconds": s["clipSeconds"], "voiceoverSeconds": s["clipSeconds"] - .1, "observed": True}
            for s in plan["scenes"]]})
        vids_batch.observe(dest, measurement)
        self.assertEqual(vids_batch.build(dest)["copiedClips"], 2)
        with self.assertRaisesRegex(ValueError, "preserve"):
            vids_chapters.prepare(self.video, dest, project_file=self.project)

    def test_embedded_audio_matches_source_at_nonkey_cut(self):
        dest = self.root / "embedded"
        receipt = vids_chapters.prepare(self.video, dest, timeline_file=self.clock, mode="embedded")
        self.assertEqual([s["audioTracks"] for s in receipt["scenes"]], [1, 1])
        self.assertTrue((dest / "handoff/placement.json").is_file())
        self.assertFalse((dest / "handoff/observed.json").exists())
        def samples(path):
            result = subprocess.run([*vids_chapters.FFMPEG, "-i", str(path), "-map", "0:a:0", "-f", "f32le", "-"],
                                    capture_output=True, check=True)
            return array("f", result.stdout)
        # Exclude AAC padding and compare the phase in the body of the second scene.
        original = samples(self.video)[33600 + 2000:33600 + 22000]
        segment = samples(dest / "clips/dos.mp4")[2000:22000]
        correlation = sum(a * b for a, b in zip(original, segment)) / math.sqrt(
            sum(a * a for a in original) * sum(b * b for b in segment))
        self.assertGreater(correlation, .99)
        with self.assertRaisesRegex(ValueError, "original audio"):
            vids_batch.init(self.root / "unwanted-batch", dest / "story.json")
        self.assertFalse((self.root / "unwanted-batch").exists())

    def test_reject_clock_or_project_mismatch_before_writing(self):
        project = read(self.project)
        project["scenes"].reverse()
        bad_project = self.root / "bad-project.json"
        write(bad_project, project)
        dest = self.root / "invalid"
        with self.assertRaisesRegex(ValueError, "IDs/order"):
            vids_chapters.prepare(self.video, dest, project_file=bad_project)
        bad_timeline = copy.deepcopy(self.timeline)
        bad_timeline["scenes"][0]["end_sample"] -= 4800
        bad_clock = self.root / "bad-clock.json"
        write(bad_clock, bad_timeline)
        with self.assertRaisesRegex(ValueError, "clocks disagree"):
            vids_chapters.prepare(self.video, dest, timeline_file=bad_clock)
        self.assertFalse(dest.exists())

    def test_chapters_required_and_must_cover_every_frame(self):
        with self.assertRaisesRegex(ValueError, "no embedded chapters"):
            vids_chapters.boundaries({}, 10, 20)
        chapters = [{"start": 0, "end": 7, "time_base": "1/10"}]
        with self.assertRaisesRegex(ValueError, "final video frame"):
            vids_chapters.boundaries({"chapters": chapters}, 10, 20)

    def test_native_millisecond_display_preserves_chapter_and_speech(self):
        source = self.root / "two-frames.mp4"
        subprocess.run([*vids_chapters.FFMPEG, "-f", "lavfi", "-i", "color=s=144x96:r=3",
                        "-frames:v", "2", "-c:v", "libx264", "-threads", "1", str(source)], check=True)
        scene = {"id": "short", "sourceClip": str(source), "sourceStartFrame": 5, "sourceEndFrameExclusive": 7,
                 "essentialAnimationSeconds": 2 / 3}
        observed = {"voiceoverSeconds": .65, "sceneSeconds": .667}
        job = vids_batch.prepare_job(self.root, {"fps": 3}, scene, observed)
        self.assertEqual(job["frames"], 2)
        observed["voiceoverSeconds"] = .667
        with self.assertRaisesRegex(ValueError, "staticHold"):
            vids_batch.prepare_job(self.root, {"fps": 3}, scene, observed)


if __name__ == "__main__":
    unittest.main()
