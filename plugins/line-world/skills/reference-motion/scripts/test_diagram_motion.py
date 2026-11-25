# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright==1.61.0", "Pillow>=10,<13"]
# ///
"""Check diagram recipes against their Canvas frames, the gallery and the export clock."""
import base64
import io
import json
import math
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

    def test_stamp_closes_gap_before_inking_and_leaves_its_own_footprint(self):
        frames = [self.stage("contact-transfer", p) for p in (0, .35, .50, .64, 1, .35)]
        rest, approach, contact, pressure, release, seek = frames
        accent = (158, 27, 50)
        self.assertEqual(seek.tobytes(), approach.tobytes())
        self.assertEqual(rest.crop((238,62,625,339)).tobytes(), release.crop((238,62,625,339)).tobytes())
        guide = (446,240,498,260)
        self.assertTrue(all(f.crop(guide).tobytes() == rest.crop(guide).tobytes() for f in frames))
        # Both the lever grip and the inked teeth travel continuously toward the sheet.
        def grip_y(image):
            return min(y for y in range(55,235) for x in range(555,606) if image.getpixel((x,y)) == accent)
        self.assertTrue(grip_y(rest) < grip_y(approach) < grip_y(contact))
        for x in (441, 471, 501):
            def tooth_bottom(image):
                return max(y for y in range(280,380) if image.getpixel((x,y)) == accent)
            self.assertTrue(tooth_bottom(rest) < tooth_bottom(approach) < tooth_bottom(contact))
            self.assertEqual(tooth_bottom(contact), 379)
            self.assertNotEqual(contact.getpixel((x,381)), accent)
            self.assertEqual(pressure.getpixel((x,381)), accent)
            self.assertEqual(release.getpixel((x,381)), accent)
        self.assertNotEqual(release.getpixel((459,381)), accent)
        self.assertNotEqual(release.getpixel((489,381)), accent)
        label = self.defaults["contact-transfer"]["labels"][-1]
        self.assertNotIn(label, [r[0] for r in self.drawn_text("contact-transfer", {}, .50)])
        self.assertIn(label, [r[0] for r in self.drawn_text("contact-transfer", {}, .65)])

    def test_linear_drive_advances_target_only_while_faces_touch(self):
        kind = "contact-transfer"
        props = {**self.defaults[kind], "drive": "linear", "effect": "displace"}
        accent, ink = (158,27,50), (51,62,72)
        def frame(p):
            png = self.direct_frame(kind, props, p * props["duration"], (960,540))
            return Image.open(io.BytesIO(png)).convert("RGB")
        rest, approach, contact, halfway, pressed, released = [frame(p) for p in (0,.35,.50,.57,.68,1)]
        def target_y(image):
            return min(y for y in range(350,423) if image.getpixel((471,y)) == accent)
        self.assertEqual([target_y(f) for f in (rest,approach,contact,halfway,pressed,released)],
                         [380,380,380,394,408,408])
        for f in (contact,halfway,pressed):
            self.assertEqual(f.getpixel((471,target_y(f)-1)), ink)
        self.assertNotEqual(released.getpixel((471,407)), ink)
        self.assertEqual(rest.crop((237,63,600,338)).tobytes(), released.crop((237,63,600,338)).tobytes())
        for field, invalid in (("drive","rope"),("effect",None),("effect",["mark"])):
            with self.assertRaisesRegex(ValueError, field):
                check_props(kind, {**props,field:invalid}, set())

    def test_rigid_rectangles_keep_identity_scale_and_exposed_area_while_swapping(self):
        kind = "rigid-rearrangement"
        swap = [
            {"id":"a","label":"Uno","width":2,"height":1,"from":[-2,0],"to":[2,0]},
            {"id":"b","label":"Dos","width":1,"height":1,"from":[2,0],"to":[-2,0]},
            {"id":"c","label":"Base","width":2,"height":2,"from":[0,0],"to":[0,0]},
        ]
        for pieces in (self.defaults[kind]["pieces"], swap):
            props = dict(duration=5, unit="cm", pieces=pieces)
            check_props(kind, props, set())
            poses = self.page.evaluate("""props => {
                const canvas=document.createElement('canvas'); canvas.width=960; canvas.height=540;
                const g=canvas.getContext('2d'), result=[];
                let marks, labels;
                g.fillRect=(x,y,w,h)=>{if(w<960) marks.push([x,y,w,h,g.fillStyle]);};
                g.fillText=(value,x,y)=>labels.push([value,x,y]);
                for(let frame=0;frame<=120;frame++){
                    marks=[]; labels=[];
                    LineWorldPresets.drawArtifact(g,'rigid-rearrangement',frame/24,props);
                    result.push([marks,labels]);
                }
                return result;
            }""", props)
            opening = poses[0][0]
            self.assertEqual(len(opening), len(pieces))
            scale = opening[0][2]/pieces[0]["width"]
            area = sum(v["width"]*v["height"] for v in pieces)
            expected_total = f"{area} cm²"
            expected_readout = next(text for text in poses[0][1] if text[0] == expected_total)
            for marks, labels in poses:
                self.assertIn(expected_readout, labels)
                for i, ((x,y,w,h,color), v) in enumerate(zip(marks,pieces)):
                    self.assertAlmostEqual(w, v["width"]*scale)
                    self.assertAlmostEqual(h, v["height"]*scale)
                    self.assertEqual(color, opening[i][-1])
                    self.assertIn([v["label"],x+w/2,y+h/2], labels)
                    for a,b,c,d,_ in marks[:i]:
                        self.assertTrue(min(x+w,a+c)-max(x,a) < 1e-7 or min(y+h,b+d)-max(y,b) < 1e-7)
            for i,v in enumerate(pieces):
                x,y = opening[i][:2]
                a,b = poses[-1][0][i][:2]
                self.assertAlmostEqual((a-x)/scale,v["to"][0]-v["from"][0])
                self.assertAlmostEqual((y-b)/scale,v["to"][1]-v["from"][1])
            self.assertNotEqual(poses[0], poses[60])
            self.assertNotEqual(poses[60], poses[-1])
            recipe = {"version":1,"scenes":[{"id":"swap","artifact":kind,"props":props}]}
            plan = load(self.page,recipe,ROOT,self.defaults,self.transitions)
            audit = self.page.evaluate("() => MotionRecipe.reading(0)")
            self.assertIn(expected_total,audit["labels"])
            self.assertIn(plan["scenes"][0]["reveal"],audit["frames"])

    def test_pivot_marker_follows_the_signed_arc_from_the_declared_zero(self):
        for orientation,start,sweep in (("compass",30,-135),("cartesian",-45,210),("cartesian",80,720)):
            props = dict(unit="mm",radius=17.5,startAngle=start,sweepAngle=sweep,duration=6,orientation=orientation)
            poses = self.page.evaluate("""props => {
              const canvas=document.createElement('canvas'); canvas.width=960; canvas.height=540;
              const g=canvas.getContext('2d'), captureArc=g.arc.bind(g);
              let arcs,texts;
              g.arc=(...args)=>{arcs.push(args);captureArc(...args);};
              g.fillText=(value,x,y)=>texts.push([value,x,y]);
              return [0,.49,1,.49].map(p => {
                arcs=[]; texts=[];
                LineWorldPresets.drawArtifact(g,'pivot-rotation',p*props.duration,props);
                return {orbit:arcs[0],traces:arcs.filter(a=>a[2]===arcs[0][2]),
                        tip:arcs.find(a=>a[2]===10).slice(0,2),texts};
              });
            }""",props)
            self.assertEqual(poses[1],poses[3])
            readout = next(t for t in poses[0]["texts"] if t[0]=="17,5 mm")
            for pose,fraction in zip(poses,[0,.5,1,.5]):
                self.assertEqual(pose["orbit"], poses[0]["orbit"])
                cx,cy,r = pose["orbit"][:3]
                x,y = pose["tip"]
                degrees = start+sweep*fraction
                theta = math.radians(degrees-90 if orientation=="compass" else -degrees)
                self.assertAlmostEqual(x,cx+r*math.cos(theta))
                self.assertAlmostEqual(y,cy+r*math.sin(theta))
                self.assertIn(readout,pose["texts"])
                if fraction:
                    self.assertEqual(len(pose["traces"]),2)
                    arc = pose["traces"][-1]
                    self.assertAlmostEqual(abs(arc[4]-arc[3]), math.radians(min(abs(sweep*fraction),360)))
                    self.assertEqual(arc[5],(orientation=="cartesian") == (sweep>0))
                else:
                    self.assertEqual(len(pose["traces"]),1)

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

    def test_named_route_visits_fixed_stations_and_holds_the_returned_object(self):
        from adapt_motion import adapt
        from narration_poses import bind, pose_at
        kind = "object-route"
        spec = {"objectLabel":"Quartz proof","stops":["Roca","Lince","Arce","Roca"]}
        recipe, report = adapt({"brief":"Its workshop itinerary","title":"Visit sequence","content":spec})
        self.assertEqual((report["status"],report["artifact"]), ("recipe",kind))
        props = recipe["scenes"][0]["props"]
        self.assertEqual(props["stops"], spec["stops"])
        self.assertEqual(props["title"], "Visit sequence")
        def positions(p):
            runs = self.drawn_text(kind, props, p)
            self.assertCountEqual([t for t, _, _ in runs], ["Visit sequence","Roca","Lince","Arce","Quartz proof"])
            return {text:(x,y) for text,x,y in runs}
        entry = positions(0)
        early = positions(.16)
        stops = [entry[k][0] for k in spec["stops"]]
        marker_y = entry["Quartz proof"][1]
        # One moving label remains attached to the same painted marker in flight and at the stops.
        for leg, (a,b) in enumerate(zip(stops,stops[1:])):
            for local in (.12,.48,.85,.98):
                p = (leg + local)/3
                runs = positions(p)
                self.assertEqual([runs[k] for k in spec["stops"]], [entry[k] for k in spec["stops"]])
                x,y = runs["Quartz proof"]
                if local == .48:
                    self.assertAlmostEqual(x,(a+b)/2)
                    self.assertLess(y,marker_y)
                else:
                    self.assertEqual((x,y),(a if local == .12 else b,marker_y))
                png = self.direct_frame(kind, props, p * props["duration"], (960,540))
                frame = Image.open(io.BytesIO(png)).convert("RGB")
                self.assertEqual(frame.getpixel((round(x+6),round(y+34))), (158,27,50))
        self.assertEqual(positions(.95)["Quartz proof"], entry["Quartz proof"])
        self.assertEqual(positions(.16),early)
        cues = [{"target":"visit-2","mention_s":2.01},{"target":"Arce","mention_s":4.02},
                {"target":"visit-4","mention_s":6.04,"role":"result","hold_s":.8}]
        result = bind(recipe["scenes"][0],{"duration_s":8,"cues":cues},24)
        for i,cue in enumerate(result["cues"]):
            self.assertAlmostEqual(pose_at(result["pose_clock"],cue["frame"]/192), (i+.78)/3)
        with self.assertRaisesRegex(ValueError,"visit-1"):
            bind(recipe["scenes"][0],{"duration_s":8,"cues":[{"target":"Roca","mention_s":1}]},24)
        for invalid in (["A"],["A","A"],["","B"],["A",3],[str(i) for i in range(9)]):
            with self.assertRaisesRegex(ValueError,"stops"):
                check_props(kind, {**props,"stops":invalid}, set())
        check_props(kind, {**props,"stops":["A","B","B","A"]}, set())
        with self.assertRaisesRegex(ValueError,"objectLabel"):
            check_props(kind, {**props,"objectLabel":""}, set())

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
