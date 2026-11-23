"""Exercise native cue painting, time-dependent reading areas and a true obstruction."""
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from review_caption_overlay import display_size, footprint, regions_from, review, sample_times


class CaptionOverlayTests(unittest.TestCase):
    def test_sample_at_region_and_simultaneous_cue_changes(self):
        cues=[{"startMs":200,"endMs":800},{"startMs":400,"endMs":600}]
        regions=[{"id":"dato","box":[0,0,1,1],"startMs":500,"endMs":700}]
        self.assertEqual(list(sample_times(cues,regions)),[
            (300,[0]),(450,[0,1]),(550,[0,1]),(650,[0]),(750,[0])])
        fine=list(sample_times(cues,regions,80))
        self.assertTrue(all(right[0]-left[0]<=80 for left,right in zip(fine,fine[1:])))
        with self.assertRaises(ValueError):list(sample_times(cues,regions,0))

    def test_aspect_ratio_at_a_phone_width(self):
        self.assertEqual(display_size({"width":1280,"height":720},360),{"width":360,"height":203})
        self.assertEqual(display_size({"width":390,"height":844},360),{"width":360,"height":780})
        for width in (0, -1, 2.5, True):
            with self.assertRaises(ValueError):
                display_size({"width":1280,"height":720},width)

    def test_visible_footprint_and_source_ink_are_distinct(self):
        before=np.full((5,10,3),255,dtype=np.uint8)
        before[3,5]=120
        after=before.copy()
        after[3,4:7]=5
        areas=regions_from([{"id":"precio","box":[.4,.6,.3,.2]},{"id":"título","box":[0,0,1,.4]}])
        result=footprint(before,after,areas)
        self.assertEqual(result["subtitleBox"],[4,3,7,4])
        self.assertEqual([(r["id"],r["changedPixels"],r["changedDarkPixels"]) for r in result["intersections"]],
                         [("precio",3,1)])
        with self.assertRaises(ValueError):footprint(before,before,areas)
        for invalid in ([1,0,.2,.5],[0,0,0,.5],[0,0,float("nan"),.5]):
            with self.assertRaises(ValueError):regions_from([{"id":"dato","box":invalid}])

    def test_channelwise_footprint_agrees_with_signed_pixel_difference(self):
        rng=np.random.default_rng(571)
        before=rng.integers(0,256,(64,92,3),dtype=np.uint8)
        after=before.copy()
        after[9:41,5:52,:]=rng.integers(0,256,(32,47,3),dtype=np.uint8)
        changed=np.max(np.abs(before.astype(np.int16)-after.astype(np.int16)),axis=2)>12
        expected_dark=(before.max(axis=2)<195)&changed
        region=[{"id":"page","box":[0,0,1,1]}]
        measured=footprint(before,after,region)
        self.assertEqual(measured["subtitleBox"],[5,9,52,41])
        self.assertEqual(measured["changedPixels"],int(changed.sum()))
        self.assertEqual(measured["intersections"][0]["changedDarkPixels"],int(expected_dark.sum()))

    def test_real_player_obscures_bottom_not_top(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/"medición #1.srt"
            source.write_text("1\n00:00:00,100 --> 00:00:00,860\nEl dato de hoy.\n\n"
                              "2\n00:00:00,900 --> 00:00:01,800\nLa fecha al pie.\n",encoding="utf-8")
            movie=root/"medición #1.mp4"
            subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=white:size=320x180:rate=12:duration=2",
                "-i",str(source),"-map","0:v","-map","1:s","-vf","drawbox=x=80:y=168:w=160:h=4:color=gray:t=fill",
                "-threads","1","-c:v","libx264","-pix_fmt","yuv420p","-c:s","mov_text","-metadata:s:s:0","language=spa",
                str(movie)],check=True)
            areas=[{"id":"leyenda","box":[.3,.93,.4,.07],"endMs":850},{"id":"título","box":[0,0,1,.3]}]
            result=review(movie,areas,"spa")
            self.assertEqual(result["cues"],2)
            small=review(movie,areas,"spa",display_width=180)
            self.assertEqual(small["size"],{"width":320,"height":180})
            self.assertEqual(small["displaySizeCssPx"],{"width":180,"height":102})
            self.assertTrue(all(r["subtitleBox"][2]<=180 and r["subtitleBox"][3]<=102 for r in small["samples"]))
            with_hit=[r for r in result["samples"] if r["intersections"]]
            self.assertTrue(with_hit)
            self.assertTrue(all(r["cues"]==[1] for r in with_hit))
            self.assertTrue(all(i["id"]=="leyenda" for r in with_hit for i in r["intersections"]))
            self.assertTrue(any(i["changedDarkPixels"]>0 for r in with_hit for i in r["intersections"]))
            self.assertTrue(any(r["cues"]==[2] and not r["intersections"] for r in result["samples"]))


if __name__=="__main__":
    unittest.main()
