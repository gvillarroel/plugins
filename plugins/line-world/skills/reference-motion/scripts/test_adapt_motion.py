"""Regression checks for transferring studied composition to new entities and measurements."""
import argparse
import json
import tempfile
import unittest
from pathlib import Path

from adapt_motion import adapt, run
from motion_recipe import compile_recipe


class TransferTests(unittest.TestCase):
    def scene(self, req):
        recipe, report=adapt(req)
        self.assertEqual(report["status"],"recipe",report)
        scene=recipe["scenes"][0]
        compile_recipe(recipe,{scene["artifact"]:{}},["cut"])
        self.assertTrue(report["direction"]["anchor"] and report["reference"]["url"])
        return scene["props"],report

    def test_opposite_directions_use_real_endpoints_and_cardinality(self):
        for outward in (True, False):
            for n in (2, 4, 6):
                names=[f"Tienda {i}" for i in range(n)]
                pairs=[("Imprenta",k) if outward else (k,"Imprenta") for k in names]
                props,report=self.scene({"brief":"Seguir las conexiones","rows":[{"desde":a,"a":b} for a,b in pairs],
                                         "fields":{"source":"desde","target":"a"}})
                self.assertEqual(report["relation"],"fan-out" if outward else "fan-in")
                by_id={v["id"]:v["label"] for v in props["nodes"]}
                self.assertEqual(set(by_id.values()),{"Imprenta",*names})
                self.assertEqual([(by_id[e["from"]],by_id[e["to"]]) for e in props["edges"]],pairs)

    def test_source_tree_differs_from_an_illustrative_tree(self):
        rows=[{"padre":a,"hijo":b} for a,b in [("Colección","Papel"),("Papel","Litografía"),
                                                ("Papel","Dibujo"),("Colección","Metal")]]
        props,rep=self.scene({"rows":rows,"brief":"Ramas de la colección"})
        self.assertEqual(rep["relation"],"hierarchy")
        root=next(x for x in props["nodes"] if x["label"]=="Colección")
        self.assertGreater(root["moveFrom"][1],root["y"])
        self.assertEqual(len(props["edges"]),4)
        for row in ([{"from":"A","to":"B"},{"from":"B","to":"A"}],rows+[rows[0]]):
            recipe,rep=adapt({"rows":row,"brief":"Trazar las conexiones"})
            self.assertIsNone(recipe)
            self.assertEqual(rep["status"],"specialist")
            self.assertEqual(rep["input"]["rows"],row)

    def test_temporal_order_is_explicit(self):
        rows=[{"from":"Museo","to":"Taller","message":"Aprobado","order":4},
              {"from":"Taller","to":"Museo","message":"Prueba","order":2}]
        p,_=self.scene({"rows":rows,"brief":"Quién envía cada mensaje"})
        self.assertEqual(p["labels"],["Taller","Museo"])
        self.assertEqual(p["exchanges"],[{"from":0,"label":"Prueba"},{"from":1,"label":"Aprobado"}])
        rows[0]["order"]=2
        self.assertIsNone(adapt({"rows":rows,"brief":"Quién envía cada mensaje"})[0])

    def test_concepts_and_measures_use_distinct_encodings(self):
        p,r=self.scene({"concepts":["Recoger","Secar","Exponer"],"brief":"Etapas en orden"})
        self.assertEqual([x["label"] for x in p["nodes"]],["Recoger","Secar","Exponer"])
        rows=[{"sede":name,"fichas":v} for name,v in [("Centro",0),("Sur",4),("Este",9)]]
        p,_=self.scene({"brief":"Comparar categorías","rows":rows,"title":"Fichas","unit":"fichas",
                        "fields":{"category":"sede","value":"fichas"},"focus":"Sur"})
        self.assertEqual(p["values"],[0,4,9])
        self.assertEqual(p["highlightIndex"],1)
        recipe,rep=adapt({"brief":"Mostrar sin movimiento","concepts":["Inicio","Final"]})
        self.assertIsNone(recipe)
        self.assertEqual(rep["status"],"static")

    def test_dated_specialist_preserves_missing_days_and_values(self):
        rows=[{"fecha":d,"valor":v} for d,v in [("2026-02-17",3),("2026-02-10",-2),("2026-02-11",None)]]
        req={"brief":"Cómo evoluciona la humedad a lo largo del tiempo","rows":rows,"unit":"%"}
        _,rep=adapt(req)
        self.assertEqual([r["value"] for r in rep["d3_chart"]["observations"]],[-2,None,3])
        self.assertEqual(rep["relation"],"time-series-reveal")
        self.assertIn("UC5xf8FbdJc",rep["reference"]["url"])
        _,duplicate=adapt({**req,"rows":rows+[rows[0]]})
        self.assertNotIn("d3_chart",duplicate)
        self.assertIn("fecha",duplicate["question"])

    def test_specialized_producer_keeps_records_and_explicit_role_bindings(self):
        rows=[{"from":"Taller","to":"Sala A","litros":8},{"from":"Taller","to":"Sala B","litros":16}]
        r,rep=adapt({"brief":"¿Qué volumen llega a cada sala?","rows":rows,"fields":{"value":"litros"},"unit":"L"})
        self.assertIsNone(r)
        self.assertEqual(rep["producer"],"line-world-d3")
        self.assertEqual(rep["input"]["rows"],rows)
        req={"brief":"Prueba de pertenencia en un filtro de Bloom","intent":"bit-probe","content":{
            "labels":["Algodón","Lana","Lino"],"bits":{"size":9,"groups":[[1,4],[4,5],[1,6]]}}}
        props,_=self.scene(req)
        self.assertEqual(props["bits"],req["content"]["bits"])
        _,insufficient=adapt({**req,"content":{"labels":["A","B","C"]}})
        self.assertEqual(insufficient["status"],"needs-input")

    def test_csv_and_report_only_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            (base/"rutas.csv").write_text("origen,destino\nPrensa,Papel\nPrensa,Cartón\n",encoding="utf-8")
            req=base/"pedido.json"
            req.write_text(json.dumps({"brief":"Recorrido","data":"rutas.csv"}),encoding="utf-8")
            args=argparse.Namespace(request=req,out=base/"escena.json",report=base/"direccion.json")
            run(args)
            self.assertEqual(json.loads(args.report.read_text(encoding="utf-8"))["relation"],"fan-out")
            with self.assertRaises(ValueError): run(args)
            with self.assertRaises(ValueError): run(argparse.Namespace(request=req,out=req,report=base/"otra.json"))
            req.write_text(json.dumps({"brief":"Cifras exactas sin movimiento","data":"rutas.csv"}),encoding="utf-8")
            args.out=base/"otra.json"; args.report=base/"estatica.json"
            run(args)
            self.assertFalse(args.out.exists())
            self.assertEqual(json.loads(args.report.read_text(encoding="utf-8"))["status"],"static")


if __name__=="__main__": unittest.main()
