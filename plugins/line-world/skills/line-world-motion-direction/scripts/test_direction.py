# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13"]
# ///
import copy
import json
import tempfile
import unittest
from pathlib import Path
from PIL import ImageColor

from direction import GRAY, RED, frame, number, read
from narrated import clock, score

EXAMPLE = Path(__file__).resolve().parents[1] / "assets/solicitud.json"


class DirectionTests(unittest.TestCase):
    def setUp(self):
        self.spec = read(EXAMPLE)

    def test_still_subject_and_full_reading_hold_across_aspects(self):
        for size in ([960, 540], [540, 960], [640, 640]):
            spec = {**self.spec, "size": size}
            anchors = set()
            for scene in spec["scenes"]:
                end = scene["cue"] + scene["move"]
                first, _, anchor = frame(spec, scene, end)
                last, _, later = frame(spec, scene, end + scene["hold"] - 1)
                self.assertEqual(first.tobytes(), last.tobytes())
                anchors.update((anchor, later))
            self.assertEqual(len(anchors), 1)

    def test_comparison_draws_a_three_to_one_ratio(self):
        beat = self.spec["scenes"][-1]
        image, _, _ = frame(self.spec, beat, beat["cue"] + beat["move"] + 3)
        lengths = []
        for paint, y in ((GRAY, 254), (RED, 346)):
            color = ImageColor.getrgb(paint)
            lengths.append(
                sum(image.getpixel((x, y)) == color for x in range(455, 850))
            )
        self.assertGreater(lengths[1], 100)
        self.assertAlmostEqual(lengths[0] / lengths[1], 3, delta=0.03)

    def test_trace_lands_on_each_measurement(self):
        beat = {**self.spec["scenes"][1], "cue": 0, "move": 41}
        positions = []
        color = ImageColor.getrgb(RED)
        for i in (0, 20, 40):
            image, _, _ = frame(self.spec, beat, i)
            pixels = [
                (x, y)
                for y in range(180, 410)
                for x in range(300, 930)
                if image.getpixel((x, y)) == color
            ]
            positions.append(
                (
                    sum(x for x, _ in pixels) / len(pixels),
                    sum(y for _, y in pixels) / len(pixels),
                )
            )
        self.assertGreater(positions[1][0], positions[0][0])
        self.assertGreater(positions[2][0], positions[1][0])
        rise1 = positions[0][1] - positions[1][1]
        rise2 = positions[0][1] - positions[2][1]
        self.assertAlmostEqual(rise1 / rise2, 21 / 24, delta=0.015)

    def test_two_visible_actions_and_only_three_with_annotation(self):
        for beat in self.spec["scenes"]:
            previous = {}
            counts = []
            for i in range(beat["cue"], beat["cue"] + beat["move"]):
                _, layers, _ = frame(self.spec, beat, i)
                if previous:
                    counts.append(sum(previous[k] != v for k, v in layers.items()))
                previous = layers
            self.assertEqual(max(counts), 3 if "note" in beat else 2)
            self.assertGreater(sum(n >= 2 for n in counts), beat["move"] / 2)

    def test_rejects_impossible_values_too_short_holds_and_duplicate_ids(self):
        for kind in ("bound", "short", "duplicate", "nonfinite"):
            spec = copy.deepcopy(self.spec)
            if kind == "bound":
                spec["scenes"][1]["values"][1] = "<2"
            if kind == "short":
                spec["scenes"][0]["hold"] = 2
            if kind == "duplicate":
                spec["scenes"][1]["id"] = spec["scenes"][0]["id"]
            if kind == "nonfinite":
                spec["scenes"][1]["values"][1] = float("nan")
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "bad.json"
                path.write_text(json.dumps(spec), encoding="utf-8")
                with self.assertRaises(ValueError):
                    read(path)

    def test_mobile_long_titles_signed_decimals_and_repeated_readings(self):
        spec = read(EXAMPLE.with_name("temperatura.json"))
        self.assertEqual(number(-1.125), "-1,125")
        self.assertEqual(number(0.00000025), "0,00000025")
        for size in ([390, 844], [720, 1280], [1280, 720], [1920, 1080]):
            spec["size"] = size
            for beat in spec["scenes"]:
                full, _, _ = frame(spec, beat, beat["cue"] + beat["move"])
                self.assertEqual(full.size, tuple(size))

    def test_all_zero_and_subpixel_comparisons_keep_true_scale(self):
        beat = self.spec["scenes"][2].copy()
        beat.pop("note")
        for values in ([0, 0], [99.95, 0.00001], [-2.5, 0], [2.5, 2.5]):
            beat["values"] = values
            observations = []
            for i in (
                beat["cue"],
                beat["cue"] + beat["move"] // 2,
                beat["cue"] + beat["move"],
            ):
                _, layers, _ = frame(self.spec, beat, i)
                observations.append(layers)
            self.assertTrue(
                all(observations[0][k] != observations[2][k] for k in observations[0])
            )
        beat["values"] = [0, 0]
        image, _, _ = frame(self.spec, beat, 99)
        color = ImageColor.getrgb(RED)
        self.assertLess(
            sum(image.getpixel((x, 346)) == color for x in range(455, 850)), 12
        )

    def test_timing_uses_absolute_samples_and_last_partial_frame(self):
        spec = read(EXAMPLE.with_name("circuito-narrado.json"))
        audio = {
            "sample_rate": 48000,
            "master": {"samples": 432017},
            "scenes": [
                {
                    "id": "interruptor",
                    "start_sample": 0,
                    "end_sample": 200000,
                    "effects": [{"absolute_start_sample": 9699}],
                    "sentences": [
                        {"absolute_start_sample": 10000, "absolute_end_sample": 195000}
                    ],
                },
                {
                    "id": "bobina",
                    "start_sample": 200000,
                    "end_sample": 432017,
                    "sentences": [
                        {
                            "absolute_start_sample": 201000,
                            "absolute_end_sample": 221000,
                        },
                        {
                            "absolute_start_sample": 244120,
                            "absolute_end_sample": 331000,
                        },
                    ],
                },
            ],
        }
        count, positions = clock(spec, audio)
        self.assertEqual((count, positions), (109, [(0, 50), (50, 109)]))
        self.assertEqual(spec["scenes"][0]["cue"], 2)
        self.assertEqual(spec["scenes"][1]["cue"], 11)
        planned = score(spec, audio, count, positions)
        self.assertEqual(planned["beats"][-1]["end"], 109)
        before, _, _ = frame(spec, spec["scenes"][0], 49)
        after, _, _ = frame(spec, spec["scenes"][1], 0)
        self.assertEqual(before.tobytes(), after.tobytes())


if __name__ == "__main__":
    unittest.main()
