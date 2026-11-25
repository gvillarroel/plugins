# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.61.0", "Pillow>=10,<13"]
# ///
"""Check diagram recipes against their Canvas frames, the gallery and the export clock."""
import base64
import io
import json
import unittest

from PIL import Image
from playwright.sync_api import Error, sync_playwright

from generate_motion import ROOT, example, image_at, launch, load, setup
from motion_recipe import DIAGRAM_LABEL_COUNTS, DIAGRAM_KINDS, check_props


def color_spans(image, y, left, right, rgb):
    """Read contiguous runs of a solid paint on a horizontal interior scan line."""
    spans = []
    for x in range(left, right):
        if image.getpixel((x, y)) == rgb:
            if spans and spans[-1][1] == x - 1:
                spans[-1][1] = x
            else:
                spans.append([x, x])
    return spans


class DiagramIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        cls.browser = launch(cls.runtime, None)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.page, self.defaults, self.transitions = setup(self.browser)
        self.addCleanup(self.page.close)

    def direct_frame(self, kind, props, seconds, size=(640, 360)):
        result = self.page.evaluate("""([kind, props, seconds, size]) => {
            const canvas = document.createElement("canvas");
            [canvas.width, canvas.height] = size;
            const ctx = canvas.getContext("2d", {willReadFrequently: true});
            LineWorldPresets.drawArtifact(ctx, kind, seconds, props, {mode: "solid"});
            return canvas.toDataURL().split(",")[1];
        }""", [kind, props, seconds, size])
        return base64.b64decode(result)

    def stage(self, kind, progress):
        props = self.defaults[kind]
        png = self.direct_frame(kind, props, progress * props["duration"], (960, 540))
        return Image.open(io.BytesIO(png)).convert("RGB")

    def test_worker_overrun_preserves_ui_cadence_and_skips_one_dispatch(self):
        before, after = (self.stage("split-clock", p) for p in (.57, .86))
        muted, accent = (105, 105, 105), (158, 27, 50)
        ui = color_spans(before, 245, 200, 900, muted)
        self.assertEqual(len(ui), 8)
        self.assertEqual(ui, color_spans(after, 245, 200, 900, muted))
        initial = color_spans(before, 370, 200, 900, accent)
        extended = color_spans(after, 370, 200, 900, accent)
        self.assertEqual((len(initial), len(extended)), (8, 7))
        self.assertGreater(initial[4][0] - initial[3][1], 25)
        self.assertEqual(extended, initial[:3] + [[initial[3][0], initial[4][1]]] + initial[5:])
        # At mid-height in the gap, a vertical dispatch is the only mark in each small window.
        def dispatches(frame):
            return [min(frame.getpixel((x, 300))[0] for x in range(left - 2, left + 5)) < 220
                    for left, _ in initial]
        self.assertEqual(dispatches(before), [True] * 8)
        self.assertEqual(dispatches(after), [True] * 4 + [False] + [True] * 3)

    def test_selected_command_shortens_towards_the_fixed_gpu_edge(self):
        poses = [self.stage("command-lanes", p) for p in (.70, .835, .94)]
        selected = []
        for image in poses:
            # Sample above the glyphs so PBR and toon never interrupt the color run.
            spans = color_spans(image, 224, 465, 918, (158, 27, 50))
            self.assertEqual(len(spans), 1)
            selected.append(spans[0])
        self.assertTrue(selected[0][0] + 25 < selected[1][0] < selected[2][0] - 25)
        self.assertEqual(len({right for _, right in selected}), 1)
        self.assertAlmostEqual(selected[0][1], 890, delta=2)
        for y in (148, 304, 382):
            lengths = [color_spans(image, y, 465, 890, (105, 105, 105)) for image in poses]
            self.assertEqual(len(lengths[0]), 1)
            self.assertEqual(lengths, [lengths[0]] * 3)

    def test_export_preserves_original_pose_motion_and_reading_hold(self):
        self.assertEqual(set(self.page.evaluate("LineWorldMotion.diagrams")), DIAGRAM_KINDS)
        for kind in sorted(DIAGRAM_KINDS):
            with self.subTest(kind=kind):
                recipe = example(kind, self.defaults, self.transitions)
                recipe.update(width=640, height=360, fps=24)
                props = recipe["scenes"][0]["props"]
                props["duration"] = 3.75
                plan = load(self.page, recipe, ROOT, self.defaults, self.transitions)
                reveal = plan["scenes"][0]["reveal"]
                self.assertEqual(reveal, 90)
                sampled = [image_at(self.page, frame) for frame in (0, 27, 61, reveal)]
                self.assertGreaterEqual(len(set(sampled)), 3)
                for frame, encoded in zip((0, 27, 61, reveal), sampled):
                    self.assertEqual(encoded, self.direct_frame(kind, props, frame / 24))
                self.assertEqual(self.page.evaluate("f => MotionRecipe.audit(f, true)", reveal), [])
                self.assertEqual(image_at(self.page, plan["frames"] - 1), sampled[-1])
                self.assertEqual(image_at(self.page, 27), sampled[1])

    def test_diagram_waits_for_an_animated_handoff(self):
        recipe = example("type-title", self.defaults, self.transitions)
        recipe.update(width=640, height=360, fps=24)
        diagram = example("module-transfer", self.defaults, self.transitions)["scenes"][0]
        diagram["transition"] = {"id": "push-left", "seconds": 1, "reason": "Seguir el módulo al inventario."}
        recipe["scenes"].append(diagram)
        plan = load(self.page, recipe, ROOT, self.defaults, self.transitions)
        begin = plan["scenes"][1]["start"] + plan["scenes"][1]["bridge"]
        opening = self.direct_frame(diagram["artifact"], diagram["props"], 0)
        self.assertEqual(image_at(self.page, begin - 1), opening)
        self.assertEqual(image_at(self.page, begin), opening)
        self.assertEqual(image_at(self.page, begin + 24), self.direct_frame(diagram["artifact"], diagram["props"], 1))

    def test_label_slots_and_duration(self):
        for kind, count in DIAGRAM_LABEL_COUNTS.items():
            with self.subTest(kind=kind):
                valid = self.defaults[kind]["labels"]
                self.assertEqual(len(valid), count)
                check_props(kind, {"labels": valid}, set())
                for labels in (valid[1:], valid + ["Extra"], [" "] + valid[1:], "texto"):
                    with self.assertRaisesRegex(ValueError, kind):
                        check_props(kind, {"labels": labels}, set())
                for duration in (0, -1, float("inf"), True):
                    with self.assertRaisesRegex(ValueError, "duration"):
                        check_props(kind, {"labels": valid, "duration": duration}, set())

    def drawn_text(self, kind, edits, progress):
        props = {**self.defaults[kind], **edits}
        return self.page.evaluate("""([kind, props, p]) => {
            const canvas = document.createElement("canvas");
            canvas.width=960; canvas.height=540;
            const ctx=canvas.getContext("2d"), runs=[];
            ctx.fillText=(text,x,y)=>runs.push([String(text),x,y]);
            LineWorldPresets.drawArtifact(ctx,kind,p*props.duration,props);
            return runs;
        }""", [kind, props, progress])

    def test_membership_query_preserves_writes(self):
        # One overlapping write, one query for a missing bit, one possible match.
        for query, result in (([1, 4], "Descartado"), ([1, 2], "Posible")):
            props = {"bits": {"size": 6, "groups": [[0, 1], [0, 2], query]}}
            before, after = [self.drawn_text("bit-probe", props, p) for p in (.60, 1)]
            cells = lambda records: [text for text, _, y in records if y == 267]
            self.assertEqual(cells(before), ["1", "1", "1", "0", "0", "0"])
            self.assertEqual(cells(before), cells(after))
            self.assertIn(result, [text for text, _, _ in after])

    def test_twenty_published_study_scenes_can_be_initialized_individually(self):
        index = json.loads((ROOT/"references/bytebytego-corpus.json").read_text(encoding="utf-8"))
        study = json.loads((ROOT/"assets/diagramas-bytebytego.json").read_text(encoding="utf-8"))
        self.assertEqual([row["index"] for row in index["videos"]], list(range(1, 21)))
        self.assertEqual(len(study["scenes"]), 20)
        for record, scene in zip(index["videos"], study["scenes"]):
            with self.subTest(scene=scene["id"]):
                self.assertEqual(record["scene"], scene["id"])
                isolated = example(record["scene"], self.defaults, self.transitions)
                self.assertEqual(isolated["scenes"], [scene])
                load(self.page, isolated, ROOT, self.defaults, self.transitions)
        with self.assertRaisesRegex(ValueError, "Escena de estudio desconocida"):
            example("video-ausente", self.defaults, self.transitions)

    def test_radix_code_uses_actual_remainders_in_reverse(self):
        for base, value, code in ((62, 11157, "2TX"), (2, 23, "10111"), (16, 254, "fe"), (2, 0, "0")):
            with self.subTest(base=base, value=value):
                runs = self.drawn_text("radix-ladder", {"base": base, "value": value}, 1)
                self.assertIn(code, [text for text, x, _ in runs if x > 700])

    def test_network_move_uses_one_clock_and_restores_anchor(self):
        props = {"nodes": [
            {"id":"left","label":"Ancla","x":.16,"y":.5,"w":.2,"h":.1},
            {"id":"right","label":"Destino","x":.8,"y":.32,"w":.2,"h":.1,
             "moveFrom":[.52,.68,.2,.8]}], "edges":[{"from":"left","to":"right"}]}
        check_props("staged-network", props, set())
        begin, mid, end, repeat = [
            {text:(x,y) for text,x,y in self.drawn_text("staged-network", props, p)}
            for p in (0, .5, 1, 0)]
        self.assertEqual(begin, repeat)
        self.assertEqual(begin["Ancla"], end["Ancla"])
        self.assertTrue(begin["Destino"][0] < mid["Destino"][0] < end["Destino"][0])
        self.assertTrue(begin["Destino"][1] > mid["Destino"][1] > end["Destino"][1])
        for move in ([.02,.5,.2,.8], [.5,.5,.8,.2]):
            with self.assertRaisesRegex(ValueError, "posición inicial|moveFrom"):
                check_props("staged-network", {**props,"nodes":[{**props["nodes"][1],"moveFrom":move}],"edges":[]}, set())

    def test_custom_labels_reach_the_drawing(self):
        for kind, count in DIAGRAM_LABEL_COUNTS.items():
            with self.subTest(kind=kind):
                labels = [f"Entidad{i}" for i in range(count)]
                drawn = self.page.evaluate("""([kind, labels]) => {
                    const canvas = document.createElement("canvas");
                    canvas.width = 1280; canvas.height = 720;
                    const ctx = canvas.getContext("2d");
                    const strings = new Set();
                    const drawText = ctx.fillText.bind(ctx);
                    ctx.fillText = (text, ...position) => {
                        strings.add(String(text)); drawText(text, ...position);
                    };
                    for (let frame = 0; frame <= 40; frame++)
                        LineWorldPresets.drawArtifact(ctx, kind, frame / 8, {duration: 5, labels});
                    return [...strings].join(" ").toLowerCase();
                }""", [kind, labels])
                for label in labels:
                    self.assertIn(label.lower(), drawn)

    def test_module_moves_the_selected_row_and_reveals_its_ports(self):
        props = self.defaults["module-transfer"]
        self.assertEqual(props["highlightIndex"], 1)
        self.assertEqual(props["inputs"], ["root", "tamaño", "objetivo"])
        self.assertEqual(props["outputs"], ["vista", "proyección"])
        for index in (0, len(props["labels"]) - 1):
            edited = {**props, "highlightIndex": index, "inputs": ["Medida"], "outputs": ["Vista", "Bordes", "Plano"]}
            check_props("module-transfer", edited, set())
            poses = self.page.evaluate("""props => {
                const canvas = document.createElement("canvas");
                canvas.width = 960; canvas.height = 540;
                const ctx = canvas.getContext("2d");
                let xs;
                ctx.fillText = function(text, x, y) {
                    xs[text] = new DOMPoint(x, y).matrixTransform(this.getTransform()).x;
                };
                return [0, props.duration].map(t => {
                    xs = {};
                    LineWorldPresets.drawArtifact(ctx, "module-transfer", t, props);
                    return xs;
                });
            }""", edited)
            start, end = poses
            chosen = props["labels"][index]
            self.assertGreater(start[chosen] - end[chosen], 300)
            for label in set(props["labels"]) - {chosen}:
                self.assertEqual(start[label], end[label])
            for port in edited["inputs"] + edited["outputs"]:
                self.assertNotIn(port, start)
                self.assertIn(port, end)
        for index in (-1, True, 1.5, len(props["labels"])):
            with self.assertRaisesRegex(ValueError, "highlightIndex"):
                check_props("module-transfer", {**props, "highlightIndex": index}, set())
        for field in ("inputs", "outputs"):
            for invalid in ([], [""], [1], "puerto", ["a"] * 4):
                with self.assertRaisesRegex(ValueError, field):
                    check_props("module-transfer", {**props, field: invalid}, set())

    def test_gallery_shows_each_diagram_and_its_source(self):
        self.page.goto((ROOT / "assets/demo.html").as_uri())
        for kind in sorted(DIAGRAM_KINDS):
            with self.subTest(kind=kind):
                self.page.evaluate("id => LineWorldDemo.select(id, 0, false)", kind)
                link = self.page.locator("#refs li a").first
                source = self.page.evaluate("id => LineWorldReferences.patterns.find(p=>p.id===id).sources[0].url", kind)
                self.assertEqual(link.get_attribute("href"), source)
                self.assertRegex(source, r"https://www.youtube.com/watch\?v=.+&t=\d+s")
                timing = self.page.evaluate("id => LineWorldDemo.timing(id)", kind)
                self.assertEqual((timing["delay"], timing["rate"]), (0, 1))
                self.assertGreater(timing["duration"], self.defaults[kind]["duration"])

    def test_import_maps_custom_overlapping_and_empty_groups(self):
        props = self.defaults["import-footprint"]
        footprint = {"total": 12, "unit": "unidades", "groups": [[0, 1, 2, 3], [2, 3, 4], []]}
        check_props("import-footprint", {**props, "footprint": footprint}, set())
        for total in (1, 240):
            boundary = {"total": total, "unit": "kB", "groups": [[total - 1], [], [total - 1]]}
            check_props("import-footprint", {**props, "footprint": boundary}, set())
        self.assertEqual(props["labels"], ["Iluminación", "Instancias", "Cámaras"])
        bad_fields = {
            "total": [0, 241, True, 12.5],
            "unit": ["", "  ", "a"*13, 7],
            "groups": [[[]], [[0], [1], "2"], [[-1], [], []], [[12], [], []],
                       [[1, 1], [], []], [[True], [], []], [[1.5], [], []]],
        }
        for field, values in bad_fields.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                    check_props("import-footprint", {**props, "footprint": {**footprint, field: value}}, set())
        for invalid in (None, {}, {**footprint, "extra": 7}):
            with self.assertRaisesRegex(ValueError, "footprint"):
                check_props("import-footprint", {**props, "footprint": invalid}, set())
        # Move one shared cell while keeping the aggregate count of each module identical.
        # The changed membership must reach the drawing at some point in the reveal.
        shifted = {**footprint, "groups": [[0, 1, 2, 3], [2, 7, 4], []]}
        def draw(spec, t):
            return self.direct_frame("import-footprint", {**props, "footprint": spec}, t)
        self.assertTrue(any(draw(footprint, i / 4) != draw(shifted, i / 4) for i in range(21)))

    def test_legacy_script_works_independently(self):
        page = self.browser.new_page()
        self.addCleanup(page.close)
        page.add_script_tag(path=str(ROOT / "assets/motion.js"))
        page.evaluate("""() => {
            const ctx = document.createElement("canvas").getContext("2d");
            LineWorldMotion.artifact(ctx, "chart-ring", 2, {value: 75, label: "Uso"});
        }""")
        with self.assertRaisesRegex(Error, r"Load diagram-motion\.js"):
            page.evaluate("""() => LineWorldMotion.artifact(
                document.createElement("canvas").getContext("2d"), "field-packing", 0)""")


if __name__ == "__main__":
    unittest.main()
