"""Regression cases for the MP4 entrance measurement."""
import importlib.util
import unittest

if importlib.util.find_spec("cv2") and importlib.util.find_spec("numpy"):
    import numpy as np
    from measure_reveal import assess, intersection, measure_pair
else:
    np = None


@unittest.skipIf(np is None, "Install the dependencies declared in measure_reveal.py.")
class EntranceTests(unittest.TestCase):
    def setUp(self):
        self.times = [n / 10 for n in range(40)]
        self.ink = [np.packbits(np.arange(400) < max(0, min(200, (n - 9) * 25))) for n in range(40)]
        self.anchor = [np.packbits(np.arange(400) < 100)] * 40

    def check(self):
        return assess(self.times, self.ink, self.anchor, 1, .7, .12, 1.8, True)

    def test_single_entry_and_read_hold(self):
        report = self.check()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["observedStartSeconds"], 1.0)
        self.assertEqual(report["settledSeconds"], 1.7)

    def test_return_to_opening_is_detected(self):
        self.ink[26] = self.ink[0]
        report = self.check()
        self.assertFalse(report["checks"]["neverReturnsToOpening"])
        self.assertFalse(report["checks"]["stableReadTime"])

    def test_instant_cut_is_not_a_slide(self):
        self.ink[10:17] = [self.ink[-1]] * 7
        self.assertFalse(self.check()["checks"]["measurableMotion"])

    def test_moving_anchor_is_detected(self):
        self.anchor[20] = self.ink[-1]
        self.assertFalse(self.check()["checks"]["anchorPresentAndStable"])

    def test_static_card_has_no_entrance(self):
        self.ink = [self.ink[-1]] * 40
        self.assertFalse(self.check()["ok"])

    def test_motion_overlap_counts_only_common_frames(self):
        self.assertAlmostEqual(intersection([[0, .5], [1, 1.5]], [[.2, .4], [.8, 1.4]]), .6)
        self.assertEqual(intersection([[0, .5]], [[.5, 1]]), 0)

    def test_same_area_cannot_count_as_two_objects(self):
        targets = [{"id": name, "revealRegion": [0, 0, 1, 1]} for name in ("price", "guide")]
        with self.assertRaisesRegex(ValueError, "disjoint"):
            measure_pair(None, {"targets": targets, "minConcurrentMotionSeconds": .1})


if __name__ == "__main__":
    unittest.main()
