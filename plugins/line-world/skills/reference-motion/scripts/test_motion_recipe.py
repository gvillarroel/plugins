"""Regression checks for unintended reversals, unreadable holds and misleading data."""
import unittest
from copy import deepcopy
import sys

sys.dont_write_bytecode=True
from motion_recipe import asset_descriptor, check_props, compile_recipe
from narration_poses import bind, pose_at


class AssetTests(unittest.TestCase):
    def test_old_paths_and_rejected_descriptors(self):
        self.assertEqual(asset_descriptor("foto.png")["focal"],[.5,.5])
        for value in ({"path":"a.png","in_s":1},{"path":"a.mp4","in_s":2,"out_s":1},
                      {"path":"a.webp","focal":[-1,0]},{"path":"a.mp4","fit":"stretch"},
                      {"path":"a.gif"},{"path":"a.mp4","out_s":False}):
            with self.subTest(value=value),self.assertRaises(ValueError):
                asset_descriptor(value)


class RecipeTests(unittest.TestCase):
    def setUp(self):
        self.spec = {"version": 1, "scenes": [
            {"id":"hora-punta", "artifact":"metric-callout", "hold":4,
             "props":{"value":"12", "label":"Salidas por hora"}},
            {"id":"comparar-horarios", "artifact":"data-chart", "hold":6,
             "transition":{"id":"push-left","seconds":2.4},
             "props":{"title":"Salidas por hora","values":[6,9,12,8],"labels":["06 h","10 h","14 h","18 h"],"highlightIndex":2}},
        ]}
        self.defaults={"metric-callout":{},"data-chart":{}}

    def compile(self):
        return compile_recipe(self.spec,self.defaults,{"cut","push-left","push-down","iris-fill"})

    def test_rigid_rearrangement_contract_and_decimal_edge_contact(self):
        valid = dict(unit="mm",pieces=[
            {"id":"a","label":"A","width":.2,"height":.25,"from":[.1,0],"to":[.1,0]},
            {"id":"b","label":"B","width":.2,"height":.25,"from":[.3,0],"to":[.1,.25]}])
        check = lambda p: check_props("rigid-rearrangement",p,set())
        check(valid)
        for field,value in [
            ("id","a"),("label",""),("from",[.29,.1]),("to",[.1,.24]),("to",[.3,0]),
            ("height",0),("width",-1),("height",True),("height",float("inf")),("width",1e-320),
            ("from",[0]),("from",[0,float("nan")]),("to","0,2"),("rotation",90)]:
            props = deepcopy(valid)
            props["pieces"][1][field] = value
            with self.subTest(field=field,value=value), self.assertRaises(ValueError):
                check(props)
        for edit in ({"unit":" "},{"pieces":[]},{"pieces":valid["pieces"][:1]}):
            with self.assertRaises(ValueError):
                check({**valid,**edit})
        scene = {"artifact":"rigid-rearrangement","props":deepcopy(valid)}
        cues = [{"target":"arrangement","role":r,"mention_s":t} for r,t in
                [("context",.2),("action",1),("result",4.01)]]
        audit = bind(scene, {"duration_s":6,"cues":cues}, 24)
        for cue,position in zip(audit["cues"],[0,.1,.88]):
            self.assertAlmostEqual(pose_at(scene["props"]["poseClock"],cue["frame"]/144),position)

    def metric_scenes(self, count):
        self.spec["scenes"] = [{"id":f"dato-{i}", "artifact":"metric-callout",
                                "props":{"value":i+1,"label":"Salidas por hora"}} for i in range(count)]
        return self.spec["scenes"]

    def test_chapters_share_a_forward_clock(self):
        plan=self.compile()
        a,b=plan["scenes"]
        self.assertEqual(a["end"],b["start"])
        self.assertEqual(a["hold"],4*24)
        self.assertEqual(b["bridge"],round(2.4*24))
        self.assertEqual(plan["frames"],b["end"])

    def test_return_needs_a_reason(self):
        back=deepcopy(self.spec["scenes"][0]);back["id"]="regreso"
        self.spec["scenes"].append(back)
        with self.assertRaisesRegex(ValueError,"A→B→A"):
            self.compile()
        back["return_reason"]="Volver a la cifra después de mostrar las otras horas."
        self.compile()

    def test_reject_cutting_the_reading_window(self):
        self.spec["scenes"][1]["hold"]=.5
        with self.assertRaisesRegex(ValueError,"lectura"):
            self.compile()

    def test_reject_rushed_movement(self):
        self.spec["scenes"][1]["transition"]["seconds"]=.25
        with self.assertRaisesRegex(ValueError,"movimiento"):
            self.compile()

    def test_reject_misaligned_series(self):
        self.spec["scenes"][1]["props"]["labels"].pop()
        with self.assertRaisesRegex(ValueError,"etiqueta"):
            self.compile()

    def test_reject_emphasis_on_missing_value(self):
        self.spec["scenes"][1]["props"]["highlightIndex"]=9
        with self.assertRaisesRegex(ValueError,"barra existente"):
            self.compile()

    def test_reject_mapping_style_in_data(self):
        self.spec["scenes"][1]["props"]["gradient"]=["black","white"]
        with self.assertRaisesRegex(ValueError,"propiedad desconocida"):
            self.compile()

    def test_footer_hold_cannot_hide_a_rushed_artifact(self):
        self.defaults["disc-endcard"]={}
        self.spec["scenes"]=[{"id":"cierre","artifact":"disc-endcard","props":{"title":"N","detail":"Norte","moveDuration":.04},"hold":10}]
        with self.assertRaisesRegex(ValueError,"desplazarse"):
            self.compile()

    def test_short_film_keeps_plain_cuts_even_with_a_usable_comparison(self):
        self.spec["scenes"][1].pop("transition")
        audit=self.compile()["transition_audit"]
        self.assertEqual((audit["joins"],audit["cuts"],audit["styled"]),(1,1,0))
        self.spec["scenes"].pop()
        audit=self.compile()["transition_audit"]
        self.assertEqual((audit["joins"],audit["effect_budget"],audit["decisions"]),(0,0,[]))

    def test_long_sequence_selects_spaced_cues_and_records_exact_frames(self):
        rows=self.metric_scenes(9)
        for i,kind in [(2,"section"),(3,"detail"),(7,"comparison")]:
            rows[i]["handoff"]=kind
        plan=self.compile()
        audit=plan["transition_audit"]
        self.assertEqual((audit["styled"],audit["cuts"],audit["effect_budget"]),(2,6,2))
        events=[d for d in audit["decisions"] if d["id"] != "cut"]
        self.assertEqual([(e["to"],e["id"],e["origin"]) for e in events],
                         [("dato-2","push-down","cue"),("dato-7","push-left","cue")])
        for s,d in zip(plan["scenes"][1:],audit["decisions"]):
            self.assertEqual((s["start"],s["bridge"]),(d["start_frame"],d["duration_frames"]))
        self.assertEqual(plan,self.compile())

    def test_manual_effect_and_explicit_cut_take_priority_over_auto_selection(self):
        rows=self.metric_scenes(6)
        rows[1]["handoff"]="detail"
        rows[2].update(handoff="comparison",transition={"id":"cut"})
        rows[4]["transition"]={"id":"push-down","reason":"Entramos en otro distrito."}
        audit=self.compile()["transition_audit"]
        self.assertEqual(audit["styled"],1)
        self.assertEqual(audit["decisions"][0]["id"],"cut")
        self.assertEqual(audit["decisions"][1]["origin"],"explicit")
        self.assertEqual(audit["decisions"][3]["reason"],"Entramos en otro distrito.")

    def test_shared_metric_protects_the_anchor_even_with_comparison_cue(self):
        metric,chart=self.spec["scenes"]
        chart.pop("transition")
        chart["handoff"]="comparison"
        self.spec["scenes"]=self.metric_scenes(2)+[metric,chart]
        audit=self.compile()["transition_audit"]
        self.assertEqual(audit["decisions"][-1]["origin"],"continuity")
        self.assertEqual(audit["styled"],0)
        chart["props"]["highlightIndex"]=0
        self.assertEqual(self.compile()["transition_audit"]["decisions"][-1]["origin"],"cue")
        chart["props"]["highlightIndex"]=2
        chart["props"]["title"]="Pasajeros por tren"
        self.assertEqual(self.compile()["transition_audit"]["decisions"][-1]["origin"],"cue")
        chart["props"]["title"]="Salidas por hora"
        chart["transition"]={"id":"iris-fill","reason":"La visita guiada solicita apertura circular."}
        self.assertEqual(self.compile()["transition_audit"]["decisions"][-1]["origin"],"explicit")

    def test_a_section_title_can_motivate_an_inferred_transition(self):
        rows=self.metric_scenes(5)
        self.defaults["type-title"]={}
        rows[3]={"id":"seccion","artifact":"type-title","props":{"title":"Otro distrito"}}
        audit=self.compile()["transition_audit"]
        self.assertEqual((audit["decisions"][2]["id"],audit["decisions"][2]["origin"]),("push-down","inferred"))

    def test_long_uniform_content_has_no_automatic_motion_to_fill_a_quota(self):
        self.metric_scenes(14)
        audit=self.compile()["transition_audit"]
        self.assertEqual((audit["styled"],audit["cuts"]),(0,13))

    def test_dense_manual_cut_list_fails_without_rewriting_requested_effects(self):
        rows=self.metric_scenes(5)
        for i in [1,4]: rows[i]["transition"]={"id":"push-down"}
        with self.assertRaisesRegex(ValueError,"Exceso de transiciones"):
            self.compile()

    def test_effects_within_budget_still_need_separating_cuts_and_reading_time(self):
        rows=self.metric_scenes(9)
        rows[1]["transition"]={"id":"push-down"}
        rows[3]["transition"]={"id":"push-left"}
        with self.assertRaisesRegex(ValueError,"dos cortes"):
            self.compile()
        rows[4]["transition"]=rows[3].pop("transition")
        self.spec["transition_policy"]={"min_gap_seconds":20}
        with self.assertRaisesRegex(ValueError,"se requieren 20 s"):
            self.compile()
        rows[3]["hold"]=10
        audit=self.compile()["transition_audit"]
        self.assertEqual(audit["styled"],2)

    def test_cuts_only_disables_suggestions_and_rejects_an_explicit_effect(self):
        rows=self.metric_scenes(5)
        self.spec["transition_policy"]={"mode":"cuts-only"}
        rows[-1]["handoff"]="section"
        self.assertEqual(self.compile()["transition_audit"]["styled"],0)
        rows[-1]["transition"]={"id":"push-down"}
        with self.assertRaisesRegex(ValueError,"presupuesto es 0"):
            self.compile()

    def test_focus_reading_time_and_endcard_scale(self):
        props=self.spec["scenes"][1]["props"]
        props["focusHold"]=2.5
        props["detail"]="Abrir el contexto con el dato aún visible."
        self.spec["scenes"][1]["hold"]=10
        self.assertEqual(self.compile()["scenes"][1]["reveal"],105)
        del props["highlightIndex"]
        with self.assertRaisesRegex(ValueError,"focusHold"):
            self.compile()
        self.defaults["disc-endcard"]={}
        self.spec["scenes"]=[{"id":"cierre","artifact":"disc-endcard","props":{"detailScale":.2}}]
        with self.assertRaisesRegex(ValueError,"detailScale"):
            self.compile()

    def test_fractional_cut_request_still_contributes_one_frame(self):
        self.spec["scenes"][1]["transition"]={"id":"cut","seconds":.0001}
        self.assertEqual(self.compile()["scenes"][1]["bridge"],1)


if __name__=="__main__":
    unittest.main()
