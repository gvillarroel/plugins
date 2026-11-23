"""Exercise palette witnesses against actual H.264 frames, including a one-frame gradient."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from review_solid_regions import inspect, regions


class SolidRegions(unittest.TestCase):
    def test_finds_exact_bad_frame_and_keeps_footage_outside_region(self):
        with tempfile.TemporaryDirectory() as tmp:
            movie=Path(tmp)/"prueba.mp4"
            pictures=[]
            red=np.array([158,27,50],dtype=np.uint8)
            for frame in range(12):
                picture=np.full((90,160,3),255,dtype=np.uint8)
                picture[12:78,8:72]=red
                # Source imagery outside the authored flat rectangle is unconstrained.
                picture[4:86,84:158]=np.random.default_rng(frame).integers(0,256,(82,74,3),dtype=np.uint8)
                if frame==7:
                    picture[12:78,8:72,0]=np.linspace(132,185,64,dtype=np.uint8)
                pictures.append(picture.tobytes())
            subprocess.run(["ffmpeg","-v","error","-threads","1","-f","rawvideo","-s","160x90","-r","12",
                "-pix_fmt","rgb24","-i","pipe:0","-vf","scale=out_color_matrix=bt709:out_range=tv",
                "-colorspace","bt709","-c:v","libx264","-crf","14","-pix_fmt","yuv420p","-threads","1",str(movie)],
                input=b"".join(pictures),check=True)
            box={"id":"cuerpo","role":"primary","box":[.10,.22,.3,.54]}
            plan={"regions":[box,{**box,"id":"antes","end":7}]}
            report=inspect(movie,plan)
            self.assertFalse(report["ok"])
            wrong,correct=report["regions"]
            self.assertEqual(wrong["failureIntervals"],[{"start":7,"end":8}])
            self.assertEqual(wrong["worstFrame"],7)
            self.assertTrue(correct["ok"],correct)
            self.assertEqual(correct["framesChecked"],7)

    def test_invalid_boxes_frames_and_palette(self):
        box={"id":"papel","color":"#ffffff","box":[.1,.1,.1,.1]}
        self.assertEqual(regions({"regions":[box]},320,180,12)[0]["pixels"],[32,18,32,18])
        for bad in ({**box,"color":"#71db30"}, {**box,"role":"surface"}, {**box,"end":13}, {**box,"box":[0,0,.001,.1]}):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                regions({"regions":[bad]},320,180,12)


if __name__=="__main__":
    unittest.main()
