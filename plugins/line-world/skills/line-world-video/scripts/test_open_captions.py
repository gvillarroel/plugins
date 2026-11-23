import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from open_captions import DEFAULT_FONT,encode,layout,prepare,probe,safe_breaks

FONT=DEFAULT_FONT


class Captions(unittest.TestCase):
    def test_number_and_joining_words_stay_together(self):
        phrase="bajó del cinco coma quince al cuatro coma noventa y dos por ciento."
        words=phrase.split()
        self.assertEqual(safe_breaks(words),[1,2,5,6])
        self.assertNotIn(1,safe_breaks("doscientas mil acciones".split()))
        self.assertNotIn(1,safe_breaks("58.798,98 €".split()))

    def test_mobile_keeps_dollar_amount_on_one_line(self):
        line="y cerró por debajo\nde los cincuenta y nueve mil dólares."
        _,result=layout({"cue":13,"text":line},FONT,390,108,21,17)
        self.assertEqual(result["lines"],line.splitlines())
        self.assertGreaterEqual(result["fontPx"],17)
        for x,y,r,b in result["boxes"]:
            self.assertGreaterEqual(min(x,y,390-r,108-b),4)

    def test_mobile_rejects_an_amount_that_cannot_fit(self):
        text=" ".join(["ciento cuarenta y nueve mil"]*6)
        with self.assertRaisesRegex(ValueError,"subtítulo 9 excede dos líneas"):
            layout({"cue":9,"text":text},FONT,390,108,21,17)

    def test_missing_font_glyph_fails_early(self):
        with self.assertRaisesRegex(ValueError,"--font"):
            layout({"cue":2,"text":"水"},FONT,390,108,21,17,spanish=False)

    def test_preexisting_output_is_protected_even_for_invalid_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/"obra.mp4"
            dest.write_bytes(b"original")
            with self.assertRaises(FileExistsError):
                encode(Path(tmp)/"no-existe.mp4",dest,FONT)
            self.assertEqual(dest.read_bytes(),b"original")

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"Requires FFmpeg and ffprobe")
    def test_normal_cli_selects_language_and_preserves_audio_chapter_and_pts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for stem,words in [("es","Un euro."),("en","One euro.")]:
                (root/(stem+".srt")).write_text(f"1\n00:00:00,270 --> 00:00:00,900\n{words}\n",encoding="utf-8")
            (root/"chapters.txt").write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/1000\nSTART=0\nEND=1000\ntitle=Part one\n",encoding="ascii")
            movie,dest=root/"original.mp4",root/"open.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=white:size=640x360:rate=24:duration=1",
                            "-f","lavfi","-i","sine=d=1","-i",str(root/"es.srt"),"-i",str(root/"en.srt"),
                            "-f","ffmetadata","-i",str(root/"chapters.txt"),"-map","0:v","-map","1:a",
                            "-map","2:s","-map","3:s","-map_chapters","4","-c:v","libx264","-threads","1",
                            "-c:a","aac","-c:s","mov_text","-metadata:s:s:0","language=spa",
                            "-metadata:s:s:1","language=eng","-disposition:s:0","0","-disposition:s:1","default",
                            str(movie)],check=True)
            plan,*_=prepare(movie)
            self.assertEqual(plan["language"],"eng")
            result=encode(movie,dest,language="spa")
            self.assertEqual(result["language"],"spa")
            self.assertEqual(result["cues"][0]["lines"],["Un euro."])
            self.assertEqual(result["cues"][0]["firstFrame"],7)
            self.assertEqual(result["cues"][0]["endFrameExclusive"],22)
            source,target=probe(movie),probe(dest)
            self.assertEqual(target["chapters"],source["chapters"])
            self.assertFalse(any(s["codec_type"]=="subtitle" for s in target["streams"]))
            def encoded_audio(path):
                return hashlib.sha256(subprocess.check_output(["ffmpeg","-v","error","-i",str(path),
                    "-map","0:a:0","-c:a","copy","-f","adts","-"])).digest()
            self.assertEqual(encoded_audio(dest),encoded_audio(movie))
            with self.assertRaisesRegex(ValueError,"language fra"):
                encode(movie,root/"missing.mp4",language="fra")
            self.assertFalse((root/"missing.mp4").exists())


if __name__=="__main__":
    unittest.main()
