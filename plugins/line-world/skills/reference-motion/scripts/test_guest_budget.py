import unittest

from motion_recipe import asset_descriptor, compile_recipe


def scene(id_, kind, props):
    return {"id": id_, "artifact": kind, "props": props}


def recipe():
    guests = [{"name": "Persona " + c, "media": c} for c in "ABCD"]
    return {"version":1, "assets":{c:c + ".mp4" for c in "ABCD"},
            "scenes":[scene("ponentes", "guest-grid", {"guests":guests})]}


def compile_(data):
    return compile_recipe(data, {"guest-grid":{}, "question-card":{}}, ["cut","push-left"])


class GuestBudgetTest(unittest.TestCase):
    def test_counts_placements_even_for_the_same_asset(self):
        data = recipe()
        with self.assertRaisesRegex(ValueError, "cuatro paneles"):
            compile_(data)
        for guest in data["scenes"][0]["props"]["guests"]:
            guest["media"] = "A"
        with self.assertRaisesRegex(ValueError, "cuatro paneles"):
            compile_(data)

    def test_the_author_can_choose_a_source_frame_or_a_portrait(self):
        data = recipe()
        for source in ("D.png", {"path":"D.mp4", "still_s":1.251}):
            data["assets"]["D"] = source
            self.assertEqual(compile_(data)["scenes"][0]["video_assets"], list("ABC"))
        for c in "ABCD":
            data["assets"][c] = c + ".png"
        self.assertEqual(compile_(data)["scenes"][0]["video_assets"], [])

    def test_selected_frame_clock_and_transition_budget(self):
        for item in [{"path":"D.png", "still_s":0}, {"path":"D.mp4", "still_s":-1},
                     {"path":"D.mp4", "still_s":1, "in_s":4}]:
            with self.assertRaisesRegex(ValueError, "still_s"):
                asset_descriptor(item)
        data = recipe()
        data["assets"]["D"] = {"path":"D.mp4","still_s":0}
        data["scenes"].insert(0, scene("intro", "question-card", {"title":"¿Quién participa?"}))
        grid = data["scenes"][-1]
        grid["transition"] = {"id":"push-left"}
        with self.assertRaisesRegex(ValueError, "la transición y tres vídeos"):
            compile_(data)
        grid["transition"] = {"id":"cut"}
        self.assertEqual(compile_(data)["scenes"][-1]["video_assets"], list("ABC"))
        data["assets"]["C"] = "C.jpg"
        grid["transition"] = {"id":"push-left"}
        self.assertEqual(compile_(data)["scenes"][-1]["video_assets"], list("AB"))

    def test_still_clock_rejects_boolean_nonfinite_and_trimmed_sources(self):
        for fields in ({"still_s": True}, {"still_s": float("nan")}, {"still_s": float("inf")},
                       {"still_s": 1, "out_s": 2}):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "still_s"):
                asset_descriptor({"path": "D.mp4", **fields})

    def test_planned_transition_obeys_the_same_budget(self):
        data = recipe()
        data["assets"]["D"] = "D.png"
        questions = [scene(f"pregunta-{i}", "question-card", {"title": f"Pregunta {i}"}) for i in range(3)]
        grid = data["scenes"][0]
        grid["handoff"] = "comparison"
        data["scenes"] = [*questions, grid]
        with self.assertRaisesRegex(ValueError, "la transición y tres vídeos"):
            compile_(data)
        data["assets"]["C"] = "C.jpg"
        self.assertEqual(compile_(data)["scenes"][-1]["transition"], "push-left")


if __name__ == "__main__":
    unittest.main()
