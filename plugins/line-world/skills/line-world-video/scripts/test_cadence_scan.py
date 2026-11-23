"""Regression clips for alternating highlights, stable cuts and one-way movement."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import numpy as np
from cadence_scan import RepeatedStates, SubjectCadence
from content_scan import scan


def picture(position, tinted=True):
    frame = np.full((90, 160, 3), 255, np.uint8)
    frame[18:20, 10:145] = 105
    frame[56:57, 10:145] = 184
    frame[31:49, 18+position:37+position] = [158, 27, 50] if tinted else [128]*3
    return frame


class CadenceTests(unittest.TestCase):
    def evaluate(self, positions, fps):
        check = RepeatedStates(fps)
        for x in positions:
            check.observe(picture(x))
        return check.report()

    def test_holds_cuts_and_one_way_pan(self):
        for positions in ([0]*30, [0]*6+[72]*40, [0]*7+[60]*7+[0]*34,
                          list(range(85)), [0]*15+[20]*15+[45]*15+[76]*15):
            with self.subTest(length=len(positions)):
                self.assertTrue(self.evaluate(positions, 30)["ok"])

    def test_return_at_native_rates_and_unequal_holds(self):
        for fps in (24, 25, 30, 60):
            for positions in ([0, 72]*12, [0]*3+[72]*5+[0]*4+[72]*3):
                report=self.evaluate(positions, fps)
                self.assertFalse(report["ok"], (fps,positions))
                interval=report["intervals"][0]
                self.assertEqual(len(interval["strongestFrames"]), 4)
                self.assertGreater(interval["changedFraction"], .01)

    def test_four_distinct_switch_poses_do_not_need_equal_dwell_times(self):
        frames=[0]+[72]*2+[0]*9+[72]
        report=self.evaluate(frames,24)
        self.assertFalse(report["ok"])
        hit=report["intervals"][0]
        self.assertEqual(hit["strongestFrames"],[0,1,3,12])
        self.assertEqual(hit["middleStepSeconds"],[2/24,9/24])
        self.assertTrue(self.evaluate([0]+[72]*30+[0]*30+[72],24)["ok"])

    def test_combined_interval_keeps_first_switch_and_later_strongest_example(self):
        checker=RepeatedStates(24)
        checker._record([0,1,2,3],.04)
        checker._record([6,7,8,9],.06)
        checker._record([2,5,8,11],.12)
        item,=checker.report()["intervals"]
        self.assertEqual((item["firstFrame"],item["lastFrame"]),(0,11))
        self.assertEqual(item["firstSwitch"],1/24)
        self.assertEqual(item["strongestFrames"],[2,5,8,11])

    def test_codec_chatter_on_a_thin_edge_and_real_thin_rules(self):
        def pulses(low, high, width):
            check=RepeatedStates(60)
            for value in [low, high, low, high]:
                frame = np.full((16,160,3), 255, np.uint8)
                frame[2:14,28:28+width] = value
                check.observe(frame)
            return check.report()
        self.assertTrue(pulses([140,75,87],[113,39,55],1)["ok"])
        self.assertTrue(pulses([255,183,203],[255,236,251],1)["ok"])
        self.assertFalse(pulses([230,230,230],[105,105,105],1)["ok"])
        self.assertFalse(pulses([140,75,87],[113,39,55],3)["ok"])

    def test_encoded_one_frame_flash_and_caching(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp)
            movie, cache = directory/"actual.mp4", directory/"cached.json"
            positions=[0]*24+[0, 72]*8+[72]*24
            cmd=["ffmpeg","-v","error","-y","-f","rawvideo","-s","160x90","-pix_fmt","rgb24",
                 "-r","24","-i","pipe:0","-c:v","libx264","-pix_fmt","yuv420p",str(movie)]
            subprocess.run(cmd,input=b"".join(picture(p).tobytes() for p in positions),check=True)
            one=scan(movie,cache=cache,policy={"width":160,"height":90})
            self.assertTrue(one["ok"])  # Separate content and cadence findings.
            self.assertFalse(one["cadence"]["ok"])
            self.assertLessEqual(one["cadence"]["intervals"][0]["start"], 26/24)
            self.assertEqual(one["frames"],len(positions))
            two=scan(movie,cache=cache,policy={"width":160,"height":90})
            self.assertEqual(one["cadence"],two["cadence"])
            self.assertTrue(two["reused"])
            self.assertIn("cadence",json.loads(cache.read_text())["result"])

    def test_subject_switches_on_a_changing_background(self):
        rng = np.random.default_rng(55)
        full = RepeatedStates(30)
        regions = SubjectCadence(30)
        label = np.zeros((90, 160), bool)
        label[32:51, 102:135] = True
        regions.configure({"etiqueta": label}, 0)
        for i in range(30):
            # The rest of the shot is changing independently of the label.
            frame = rng.integers(15, 240, (90, 160, 3), dtype=np.uint8)
            frame[label] = [125, 125, 125]
            if (i//3) % 2:
                frame[35:48, 105:132] = [158, 27, 50]
            full.observe(frame)
            regions.observe(frame)
        self.assertTrue(full.report()["ok"])
        intervals = regions.finish()
        self.assertEqual([r["subject"] for r in intervals], ["etiqueta"])
        self.assertGreaterEqual(len(set(intervals[0]["strongestFrames"])), 4)

    def test_reset_at_cut_and_ignore_overlap(self):
        mask = np.ones((48, 48), bool)
        mask[12:36, 12:36] = False
        regions = SubjectCadence(30)
        for i in range(16):
            if i in (0, 8):
                regions.configure({"rotulo": mask}, i, cut=True)
            # The flicker is confined to a different object in front of this region.
            frame = np.full((48, 48, 3), 90 if i < 8 else 190, dtype=np.uint8)
            frame[12:36, 12:36] = 20 if i % 2 else 220
            regions.observe(frame)
        self.assertEqual(regions.finish(), [])


if __name__=="__main__":
    unittest.main()
