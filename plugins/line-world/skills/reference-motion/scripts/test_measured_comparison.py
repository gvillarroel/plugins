import unittest

from adapt_motion import adapt
from staging_notes import read_staging


class MeasuredComparisonTests(unittest.TestCase):
    def test_each_rate_retains_both_source_counts_and_undefined_base(self):
        req = {"fields":{"category":"port","numerator":"late","denominator":"logged"},
               "rows":[dict(port=name, late=late, logged=logged) for name,late,logged in
                       [("A",2,5),("B",7,50),("C",0,0)]]}
        _, report = adapt(req)
        self.assertEqual([r["value"] for r in report["d3_chart"]["records"]], [40,14,None])
        self.assertEqual(report["d3_chart"]["records"][1]["denominator"], 50)
        req["rows"][0]["late"] = 9
        self.assertNotIn("d3_chart", adapt(req)[1])

    def test_paired_values_preserve_signed_zero_and_half_observed_rows(self):
        req = dict(intent="paired-change",unit="m",focus="C",
                   rows=[dict(item=k,before=a,after=b) for k,a,b in [("A",-5,0),("B",2,2),("C",None,4)]])
        chart = adapt(req)[1]["d3_chart"]
        self.assertEqual([(r["before"],r["after"]) for r in chart["records"]],[(-5,0),(2,2),(None,4)])
        self.assertEqual(chart["focus"], "r3")

    def test_concepts_with_no_supported_order(self):
        req = dict(brief="Dos opciones disponibles", concepts=["Teatro","Cine"])
        self.assertIsNone(adapt(req)[0])
        peers = adapt({**req,"conceptRelation":"peers"})[0]["scenes"][0]["props"]
        self.assertEqual(peers["edges"],[])
        self.assertEqual({n["y"] for n in peers["nodes"]},{.5})

    def test_coincident_observations_enter_together_without_a_directional_link(self):
        req=dict(concepts=["Campanada","Luz"], conceptRelation="co-occurrence",context="Durante el ensayo")
        props=adapt(req)[0]["scenes"][0]["props"]
        self.assertEqual(props["edges"],[])
        self.assertEqual(props["nodes"][0]["label"],req["context"])
        self.assertEqual([n["enter"] for n in props["nodes"][1:]],[[.18,.42],[.18,.42]])

    def test_phrases_match_the_recorded_script_order(self):
        notes=dict(claim="Subió el nivel",anchor="Orilla",poses=[
            dict(role=r,phrase=p,visual=v) for r,p,v in [
                ("context","Al principio","Orilla y nivel"),
                ("action","entró agua","Ascenso de la marca"),("result","subió","Línea de llegada")]])
        self.assertEqual(read_staging("Al principio entró agua y el nivel subió.",notes)["timing"],"script-phrases")
        with self.assertRaises(ValueError):
            read_staging("Al principio subió la escala y entró agua.",notes)


if __name__ == "__main__":
    unittest.main()
