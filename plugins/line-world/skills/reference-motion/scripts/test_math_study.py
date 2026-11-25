"""Verify the two mathematical data contracts, semantic retrieval and reversible pose clocks."""
import unittest

from adapt_motion import adapt
from math_study import COMPOSITIONS, corpus, directions
from motion_recipe import check_props
from narration_poses import resolve
from study_direction import find_direction


class MathematicsTests(unittest.TestCase):
    def test_pivot_rotation_maps_the_supplied_radius_and_signed_sweep(self):
        content = dict(unit="mm",radius=33.2,startAngle=17.25,sweepAngle=-103.75,orientation="compass")
        for brief in ("", "Girar la marca del brazo alrededor de su pivote"):
            recipe, report = adapt(dict(brief=brief,title="Giro de prueba",content=content))
            self.assertEqual(report["artifact"], "pivot-rotation")
            self.assertEqual(recipe["scenes"][0]["props"], dict(content,title="Giro de prueba",duration=6))
            self.assertIn("bnjKwiUg-kw", report["reference"]["url"])
        for edit in ({"radius":0},{"radius":True},{"startAngle":float("nan")},{"sweepAngle":0},
                     {"sweepAngle":float("inf")},{"unit":" "},{"orientation":"north"},{"pointLabel":None}):
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                check_props("pivot-rotation",dict(content,**edit),set())
        recipe,report=adapt(dict(intent="pivot-rotation",content={"unit":"mm","radius":3}))
        self.assertIsNone(recipe)
        self.assertIn("sweepAngle", report["question"])
        self.assertEqual(resolve("pivot-rotation",content,{"target":"rotation","role":"result"})[1],.88)

    def test_every_published_item_has_visual_evidence(self):
        passages = corpus()
        self.assertEqual(len({p["video_id"] for p in passages}), 60)
        for p in passages:
            a,b = p["source_s"]
            self.assertLess(a,b)
            self.assertEqual(set(p["poses"]), {"before","change","after"})
            self.assertTrue(p["anchor"] and p["url"] and p["method"])
        for key in COMPOSITIONS:
            self.assertTrue(directions("",key), key)
        self.assertTrue({p["family"] for p in passages}.issubset({f for rule in COMPOSITIONS.values() for f in rule.families}))

    def test_map_between_real_values_and_uneven_times(self):
        req = dict(brief="La trayectoria del móvil y su gráfica", unit="cm",rows=[
            dict(t=t,x=x,y=y,unidad_tiempo="s") for t,x,y in [(8,2,-4),(0,0,1),(2,3,1)]])
        recipe, report = adapt(req)
        props = recipe["scenes"][0]["props"]
        self.assertEqual(report["artifact"], "trajectory-trace")
        self.assertEqual([s["t"] for s in props["samples"]], [0,2,8])
        self.assertEqual(resolve(report["artifact"],props,dict(target="sample-2",role="result"))[1], .25)
        self.assertEqual(adapt(dict(req,brief=""))[1]["artifact"],"trajectory-trace")
        for rows in [[*req["rows"],req["rows"][0]], [*req["rows"],dict(t=9,x=None,y=0,unidad_tiempo="s")]]:
            with self.assertRaises(ValueError):
                adapt(dict(req,rows=rows))

    def test_bounds_in_both_directions_and_rejected_incomparable_ranges(self):
        intervals=[dict(label=str(n),low=a,high=b) for n,(a,b) in enumerate([(-4,12),(0,6),(0,3)])]
        for steps in (intervals,intervals[::-1]):
            recipe,report=adapt(dict(brief="Acotar intervalos anidados",content=dict(intervals=steps,unit="m")))
            self.assertEqual(recipe["scenes"][0]["props"]["intervals"],steps)
            self.assertEqual(report["reference"]["study"],"3Blue1Brown")
        rows = [dict(etapa=f"E{i}",orden=i,inferior=d["low"],superior=d["high"]) for i,d in enumerate(intervals)]
        self.assertEqual(adapt(dict(rows=rows,unit="cm"))[1]["artifact"],"interval-refinement")
        for spans in [[(0,3),(1,4)],[(1,2),(1,2)],[(1,2),(1,3),(1,2)],[(2,2),(1,4)]]:
            with self.assertRaises(ValueError):
                check_props("interval-refinement",dict(unit="s",intervals=[
                    dict(label="tramo",low=a,high=b) for a,b in spans]),set())

    def test_concept_handoff_static_and_systems_continue_to_use_their_own_routes(self):
        recipe,r=adapt(dict(brief="Demostrar un teorema geométrico",concepts=["círculos","tangentes"]))
        self.assertIsNone(recipe)
        self.assertEqual((r["relation"],r["reference"]["study"]),("geometric-proof","3Blue1Brown"))
        self.assertEqual(find_direction("El campo de una tabla"),[])
        self.assertTrue(all(r.get("study")!="3Blue1Brown" for r in find_direction("intervalos anidados","fan-out")))


if __name__=="__main__":
    unittest.main()
