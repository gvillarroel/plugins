# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "Pillow>=11,<13"]
# ///
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image, ImageDraw
from review_spoken_visuals import audit, digest, inspect_plate, movie_clock


class SpokenVisuals(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.crop = self.root/"value.png"
        self.box = [7, 9, 97, 27]
        self.plate = Image.new("RGB",tuple(self.box[2:]), "white")
        draw = ImageDraw.Draw(self.plate)
        draw.rectangle((3,10,10,11),fill="#9e1b32")
        draw.text((14,3),"13,85 %",fill="#9e1b32")
        self.plate.save(self.crop)
        self.film = self.video("temprano", False)
        self.fixed = self.video("correcto", True)
        self.plan = self.root/"plan.json"
        self.plan.write_text(json.dumps({"version":1,"plates":[{"fact":"baja","reference":self.crop.name,
                            "sha256":digest(self.crop),"box":self.box}]}))
        self.words = self.root/"voz.json"
        self.result = self.root/"revision.json"
        self.report = {"version":1,"origin":{"method":"unprompted-asr","provider":"synthetic clock fixture",
            "mediaSha256":digest(self.film),"audioStream":"a:0","clock":"seconds-from-first-decoded-sample"},
            "checks":[{"id":"baja","status":"coincide","matched":"baja","heard":[{"word":"baja","start":.075,"end":.275}]}]}
        self.words.write_text(json.dumps(self.report))

    def video(self, name, keep_sign, frequency=370):
        frames = []
        for index in range(6):
            frame = Image.new("RGB",(120,60),"white")
            frame.paste(self.plate,(7,9))
            if index==1 and not keep_sign:
                ImageDraw.Draw(frame).rectangle((10,19,17,20),fill="white")
            frames.append(frame.tobytes())
        out = self.root/(name+".mp4")
        subprocess.run(["ffmpeg","-v","error","-f","rawvideo","-pixel_format","rgb24","-video_size","120x60",
             "-framerate","10","-i","pipe:0","-itsoffset","0.2","-f","lavfi","-i",f"sine=f={frequency}:r=24000:d=1",
             "-vf","setpts=N+3*floor(N/2)","-fps_mode","vfr","-c:v","libx264rgb","-crf","0","-c:a","alac",
             "-threads","1",str(out)],input=b"".join(frames),check=True)
        return out

    def test_held_vfr_picture_with_delayed_audio_and_a_missing_minus(self):
        self.assertEqual(movie_clock(self.film)["pts"],[0,.1,.5,.6,1,1.1])
        old = audit(self.film,self.plan,self.words,None,self.result)
        self.assertAlmostEqual(old["audioStartInPictureClock"],.2)
        self.assertEqual(old["checks"][0]["frameRange"],[1,2])
        self.assertEqual(old["checks"][0]["differingFrameRanges"],[[1,2]])
        new = audit(self.fixed,self.plan,self.words,self.film,self.result)
        self.assertTrue(new["ok"])
        self.assertTrue(new["sharedDecodedPcm"].startswith("SHA256="))
        with self.assertRaisesRegex(ValueError,"differs"):
            audit(self.video("otro",True,610),self.plan,self.words,self.film,self.result)

    def test_spoken_words_extend_past_the_last_picture(self):
        self.report["checks"][0]["heard"] = [{"word":"baja", "start":.95, "end":1.18}]
        self.words.write_text(json.dumps(self.report))
        result = audit(self.fixed,self.plan,self.words,self.film,self.result)
        row = result["checks"][0]
        self.assertFalse(result["ok"])
        self.assertEqual(row["comparedFrames"],1)
        self.assertAlmostEqual(row["uncoveredMediaIntervals"][0][0],1.2)
        self.assertAlmostEqual(row["uncoveredMediaIntervals"][0][1],1.38)

    def test_review_preserves_input_and_identifies_unrecognized_words(self):
        with self.assertRaisesRegex(ValueError,"distinct"):
            audit(self.film,self.plan,self.words,None,self.crop)
        self.report["checks"][0]["status"] = "revisar"
        self.words.write_text(json.dumps(self.report))
        result = audit(self.fixed,self.plan,self.words,self.film,self.result)
        self.assertEqual(result["checks"][0]["comparedFrames"],0)
        self.assertFalse(result["ok"])
        Image.new("RGB",tuple(self.box[2:]),"white").save(self.crop)
        with self.assertRaisesRegex(ValueError,"changed"):
            audit(self.film,self.plan,self.words,None,self.result)
        with self.assertRaisesRegex(ValueError,"ink"):
            inspect_plate(self.film,self.crop,self.box,1,2)


if __name__ == "__main__":
    unittest.main()
