from pathlib import Path
import subprocess
import tempfile
import unittest
import wave

import numpy as np

from check_narrated_export import cues, verify


class NarratedExportTests(unittest.TestCase):
    def test_codec_font_tags_preserve_exact_words_and_time(self):
        timing = "1\n00:00:00,100 --> 00:00:01,800\n"
        source = timing + "La escena cambia."
        styled = timing + '<font face="Serif" size="18"><font size="0"><font color="#000000">La escena cambia.</font></font></font>'
        self.assertEqual(cues(styled), cues(source))
        self.assertNotEqual(cues(styled), cues(source.replace("cambia.", "cambió.")))
        self.assertNotEqual(cues(styled), cues(source.replace(",100", ",200")))

    def test_subtitle_clock_and_delayed_voice(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            rate=48000
            n=rate*2
            t=np.arange(n)/rate
            signal=.19*np.sin(2*np.pi*(160*t+210*t*t))*np.minimum(1,t*25)*np.minimum(1,(2-t)*25)
            wav_path=root/"master.wav"
            with wave.open(str(wav_path),"wb") as wav:
                wav.setparams((1,2,rate,0,"NONE",""))
                wav.writeframes((signal*32767).astype("<i2").tobytes())
            srt=root/"voz.srt"
            srt.write_text("1\n00:00:00,100 --> 00:00:01,800\nLa escena cambia.\n",encoding="utf-8")
            meta=root/"meta.txt"
            meta.write_text(";FFMETADATA1\n[CHAPTER]\nTIMEBASE=1/24\nSTART=0\nEND=48\ntitle=Idea\n")
            movie=root/"clip.mp4"
            scenes=[{"id":"a","title":"Idea","start":0,"end":48,"voice":{"end_sample":n}}]
            def encode(filters):
                subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i","color=s=160x90:r=24:d=2",
                    "-i",str(wav_path),"-i",str(srt),"-f","ffmetadata","-i",str(meta),"-map","0:v:0",
                    "-map","1:a:0","-map","2:s:0","-map_chapters","3",*filters,"-c:v","libx264","-c:a","aac",
                    "-b:a","160k","-c:s","mov_text","-metadata:s:a:0","language=spa","-metadata:s:s:0",
                    "language=spa",str(movie)],check=True)
            encode([])
            original=verify(movie,wav_path,srt,scenes,24,"spa",rate)
            self.assertTrue(original["ok"],original)
            srt.write_text("1\n00:00:00,400 --> 00:00:01,800\nLa escena cambia.\n",encoding="utf-8")
            self.assertFalse(verify(movie,wav_path,srt,scenes,24,"spa",rate)["captionsMatch"])
            encode(["-af","adelay=80,atrim=end=2"])
            damaged=verify(movie,wav_path,srt,scenes,24,"spa",rate)
            self.assertTrue(damaged["captionsMatch"])
            self.assertFalse(damaged["audio"][0]["ok"])


if __name__=="__main__":
    unittest.main()
