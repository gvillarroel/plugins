import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from batch_clips import sha
from vids_tracks import inventory, packet_receipt, restore, srt


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg tools required")
class TrackRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.native = cls.root / "native.mp4"
        cls.reviewed = cls.root / "reviewed.mp4"
        cls.srt_file = cls.root / "author.srt"
        cls.srt_file.write_text("1\n00:00:00,150 --> 00:00:00,800\n¿Por qué?\n\n"
                                "2\n00:00:01,010 --> 00:00:01,700\nCinco coma quince.\n", encoding="utf-8")
        english = cls.root / "english.srt"
        english.write_text("1\n00:00:00,100 --> 00:00:00,900\nKeep English.\n", encoding="utf-8")
        wrong = cls.root / "auto.srt"
        wrong.write_text("1\n00:00:00,100 --> 00:00:00,900\nTexto incompleto.\n", encoding="utf-8")
        chapters = cls.root / "chapters.ffmeta"
        chapters.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=Pregunta\n"
                            "[CHAPTER]\nTIMEBASE=1/1000\nSTART=1000\nEND=2000\ntitle=Respuesta\n", encoding="utf-8")
        ff = ["ffmpeg", "-nostdin", "-v", "error", "-threads", "1"]
        subprocess.run([*ff, "-f", "lavfi", "-i", "testsrc2=size=128x72:rate=15:duration=2",
                        "-f", "lavfi", "-i", "sine=d=2", "-f", "lavfi", "-i", "sine=f=600:d=2",
                        "-i", str(wrong), "-i", str(english), "-map", "0:v", "-map", "1:a", "-map", "2:a",
                        "-map", "3:s", "-map", "4:s", "-c:v", "libx264", "-threads", "1", "-c:a", "aac",
                        "-c:s", "mov_text", "-metadata:s:s:0", "language=spa", "-metadata:s:s:1", "language=eng",
                        str(cls.native)], check=True)
        subprocess.run([*ff, "-i", str(cls.native), "-i", str(cls.srt_file), "-f", "ffmetadata", "-i", str(chapters),
                        "-map", "0:v", "-map", "0:a:0", "-map", "1:s", "-map_chapters", "2", "-c", "copy",
                        "-c:s", "mov_text", "-metadata:s:s:0", "language=spa", str(cls.reviewed)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_cli_replaces_captions_restores_chapters_and_preserves_all_other_media(self):
        target = self.root / "restored.mp4"
        original = sha(self.native)
        script = Path(__file__).with_name("vids_delivery.py")
        data = json.loads(subprocess.check_output([sys.executable, str(script), "restore-tracks", "--video", str(self.native),
                          "--reference", str(self.reviewed), "--language", "spa", "--output", str(target)]))
        self.assertEqual((data["status"], data["cueCount"]), ("local-reviewed-derivative", 2))
        self.assertEqual([ch["title"] for ch in data["chapters"]], ["Pregunta", "Respuesta"])
        self.assertEqual([s["codec"] for s in data["copiedStreams"]], ["h264", "aac", "aac", "mov_text"])
        retained = inventory(target)["streams"]
        self.assertEqual(srt(target, retained[3]["index"]), srt(self.native, 4))
        self.assertEqual(srt(target, retained[4]["index"]), srt(self.srt_file, 0))
        self.assertEqual(original, sha(self.native))
        saved = sha(target)
        with self.assertRaisesRegex(ValueError, "exists"):
            restore(self.native, self.reviewed, "spa", target)
        self.assertEqual(saved, sha(target))

    def test_standalone_vtt_keeps_native_chapters_and_audio_trim(self):
        vtt = self.root / "new.vtt"
        vtt.write_text("WEBVTT\n\n00:00:00.321 --> 00:00:01.234\nCambio con acento.\n", encoding="utf-8")
        target = self.root / "sidecar.mp4"
        done = restore(self.reviewed, vtt, "spa", target)
        self.assertEqual(len(done["chapters"]), 2)
        self.assertEqual(srt(target, 2), srt(vtt, 0))
        old, new = inventory(self.reviewed)["streams"][1], inventory(target)["streams"][1]
        self.assertEqual(packet_receipt(self.reviewed, old), packet_receipt(target, new))

    def test_incompatible_or_wrong_language_inputs_leave_no_output(self):
        target = self.root / "rejected.mp4"
        with self.assertRaisesRegex(ValueError, "identifiable"):
            restore(self.native, self.reviewed, "fra", target)
        long = self.root / "long.srt"
        long.write_text("1\n00:00:00,100 --> 00:00:02,800\nFuera de tiempo.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "beyond"):
            restore(self.native, long, "spa", target)
        self.assertFalse(target.exists())
        with self.assertRaisesRegex(ValueError, "separate"):
            restore(self.native, self.reviewed, "spa", self.native)

    def test_cli_delays_only_the_reviewed_language(self):
        dest = self.root / "delayed.mp4"
        cli = Path(__file__).with_name("vids_delivery.py")
        report = json.loads(subprocess.check_output([sys.executable, str(cli), "restore-tracks", "--video", str(self.native),
            "--reference", str(self.reviewed), "--language", "spa", "--caption-offset-ms", "+82", "--output", str(dest)]))
        self.assertEqual(report["captionOffsetMs"], 82)
        self.assertNotEqual(report["referenceTimedTextSha256"], report["timedTextSha256"])
        delivered = srt(dest, 4)
        self.assertIn("00:00:00,232 --> 00:00:00,882\n¿Por qué?", delivered)
        self.assertIn("00:00:01,092 --> 00:00:01,782\nCinco coma quince.", delivered)
        self.assertEqual(srt(dest, 3), srt(self.native, 4))
        self.assertEqual([ch["start"] for ch in report["chapters"]], ["0", "1"])

    def test_advance_to_zero_or_delay_to_end_preserves_entire_cues(self):
        for offset, start, end in [(-150, "00:00:00,000 --> 00:00:00,650", "00:00:00,860 --> 00:00:01,550"),
                                   (300, "00:00:00,450 --> 00:00:01,100", "00:00:01,310 --> 00:00:02,000")]:
            with self.subTest(offset=offset):
                dest = self.root / f"edge-{offset}.mp4"
                restore(self.reviewed, self.reviewed, "spa", dest, offset)
                self.assertIn(start, srt(dest, 2))
                self.assertIn(end, srt(dest, 2))

    def test_offsets_outside_the_movie_reject_instead_of_truncating(self):
        for offset, cue in [(-151, 1), (301, 2)]:
            with self.subTest(offset=offset):
                dest = self.root / "out-of-range.mp4"
                with self.assertRaisesRegex(ValueError, f"Cue {cue}"):
                    restore(self.native, self.reviewed, "spa", dest, offset)
                self.assertFalse(dest.exists())


if __name__ == "__main__":
    unittest.main()
