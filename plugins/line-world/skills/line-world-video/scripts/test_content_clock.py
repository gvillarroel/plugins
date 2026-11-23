"""Use actual VFR and offset media to test picture timing and alternating cards."""
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np

from content_scan import scan


def render_case(name, root, size, ticks, states):
    """Each tick is 1/25 s. An audio stream starting at zero preserves late images."""
    width,height=size
    pictures=[]
    for state in states:
        rgb=np.full((height,width,3),255,np.uint8)
        if state!="blank":
            left=width//8 if state=="a" else width//2
            rgb[height//3:2*height//3,left:left+width//4]=[158,27,50]
        pictures.append(rgb.tobytes())
    expression=str(ticks[-1])
    for frame in reversed(range(len(ticks)-1)):
        expression=f"if(eq(N,{frame}),{ticks[frame]},{expression})"
    path=root/(name+".mp4")
    subprocess.run(["ffmpeg","-v","error","-y","-f","rawvideo","-pixel_format","rgb24","-s",f"{width}x{height}",
                    "-framerate","25","-i","pipe:0","-f","lavfi","-i","anullsrc=r=48000:d=2",
                    "-vf",f"setpts='{expression}'","-fps_mode","vfr","-threads","1","-c:v","libx264",
                    "-pix_fmt","yuv420p","-c:a","aac",str(path)],input=b"".join(pictures),check=True)
    return path


class ContentClockTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_native_offset_and_unequal_short_holds_are_detected(self):
        movie=render_case("rapido",self.root,(160,96),[10,19,20,27,29],["a","a","b","a","b"])
        report=scan(movie,policy={"width":160,"height":96})
        self.assertEqual(report["frames"],5)
        self.assertTrue(report["ok"])
        hit=report["cadence"]["intervals"][0]
        self.assertEqual(hit["strongestFrames"],[1,2,3,4])
        self.assertAlmostEqual(hit["firstSwitch"],.8)
        self.assertAlmostEqual(hit["middleStepSeconds"][0],.28)
        self.assertAlmostEqual(hit["middleStepSeconds"][1],.08)
        self.assertAlmostEqual(report["firstPicture"],.4)
        self.assertLess(report["pictureEnd"],2)

    def test_held_state_over_half_a_second_is_a_reading_hold(self):
        movie=render_case("pausa",self.root,(160,96),[0,1,17,19,20],["a","b","a","b","b"])
        report=scan(movie,policy={"width":160,"height":96})
        self.assertEqual(report["frames"],5)
        self.assertTrue(report["cadence"]["ok"])

    def test_blank_intervals_and_portrait_aspect_ratio_use_the_actual_pictures(self):
        movie=render_case("hueco",self.root,(96,160),[4,6,12,25],["a","blank","blank","b"])
        report=scan(movie)
        self.assertEqual(report["frames"],4)
        self.assertEqual(report["insufficientFrames"],2)
        interval,=report["intervals"]
        self.assertEqual((interval["firstFrame"],interval["lastFrame"]),(1,2))
        self.assertAlmostEqual(interval["start"],.24)
        self.assertAlmostEqual(interval["end"],1)
        self.assertAlmostEqual(report["policy"]["width"]/report["policy"]["height"],96/160,places=2)


if __name__=="__main__":
    unittest.main()
