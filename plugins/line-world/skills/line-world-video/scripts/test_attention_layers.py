"""Check an opaque fixed label over a moving picture as two separately observable subjects."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import subprocess

import numpy as np
from review_attention import inspect, validate, visible_regions


def plan():
    return {"fps":12,"frames":24,"tracks":{"picture":{"box":[0,0,1,1]},
            "scale":{"box":[.1,.6,.65,.3],"occludes":["picture"]}},
            "beats":[{"start":0,"end":12,"focus":"scale","mode":"motion","moving":["picture","scale"],
                      "idea":"The indicator follows one second of moving footage."},
                     {"start":12,"end":24,"focus":"scale","mode":"read","moving":["picture"],
                      "idea":"Read the final position while the picture continues."}]}


def encode(path, *, leak=False, flash=False):
    with subprocess.Popen(["ffmpeg","-v","error","-y","-f","rawvideo","-pix_fmt","rgb24","-s","240x100","-r","12","-i","-",
         "-c:v","libx264","-crf","12","-threads","1","-pix_fmt","yuv420p",str(path)],stdin=subprocess.PIPE) as proc:
        for i in range(24):
            rgb=np.full((100,240,3),190,np.uint8)
            rgb[:,(np.arange(240)+i*2)%90<25]=[40,92,53]
            if not leak:
                rgb[60:90,24:180]=255
            x=28+min(11,i)*9
            if flash and i>=12:
                x=30 if i%2 else 120
            rgb[67:82,x:x+20]=[158,27,50]
            proc.stdin.write(rgb.tobytes())
        proc.stdin.close()
        if proc.wait():
            raise RuntimeError("FFmpeg failed to encode the test fixture.")


class AttentionLayers(unittest.TestCase):
    def test_opaque_plate_and_source_fidelity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"layers.mp4"
            score=validate(plan())
            encode(p)
            report=inspect(p,score)
            self.assertTrue(report["ok"],report["issues"])
            self.assertEqual(report["seconds"][0]["beats"][0]["peakSimultaneous"],2)
            self.assertEqual(report["seconds"][1]["beats"][0]["peakSimultaneous"],1)
            self.assertEqual(report["occlusions"],{"scale":["picture"]})
            encode(p,leak=True)
            leaked=inspect(p,score)
            self.assertTrue(any("scale" in i["detail"] for i in leaked["issues"] if i["code"].startswith("unplanned-")))
            encode(p,flash=True)
            flicker=inspect(p,score)
            self.assertTrue(any(i["code"]=="rapid-subject-alternation" and i["detail"]["subject"]=="scale"
                                for i in flicker["issues"]))

    def test_undeclared_duplicate_cyclic_and_large_layer_counts(self):
        score=plan()
        broken=deepcopy(score)
        broken["tracks"]["picture"]["occludes"]=["scale"]
        with self.assertRaisesRegex(ValueError,"cycle"):
            validate(broken)
        for behind in (["other"],["scale"],["picture","picture"]):
            broken=deepcopy(score)
            broken["tracks"]["scale"]["occludes"]=behind
            with self.subTest(behind=behind),self.assertRaisesRegex(ValueError,"occludes"):
                validate(broken)
        names=[str(i) for i in range(257)]
        masks={n:np.ones((3,3),dtype=bool) for n in names}
        coverage,owned=visible_regions(names,{n:{} for n in names},masks,(3,3))
        self.assertEqual(coverage[0,0],257)
        self.assertFalse(any(mask.any() for mask in owned.values()))


if __name__=="__main__":
    unittest.main()
