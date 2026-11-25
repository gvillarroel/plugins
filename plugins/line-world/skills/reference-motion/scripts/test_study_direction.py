"""Check cross-domain retrieval against measured passages in the shipped corpus."""
import unittest

from study_direction import FAMILY_EXAMPLES, RULES, evidence_for, find_direction, passages


class StudyDirectionTests(unittest.TestCase):
    def test_every_reference_has_a_retrieval_rule_and_reproducible_start(self):
        self.assertEqual(set(passages()), set(RULES))
        self.assertEqual(len(passages()), 40)
        for key, (video_id, passage) in passages().items():
            with self.subTest(key=key):
                result = evidence_for(key)
                self.assertEqual(result["video_id"], video_id)
                self.assertEqual(result["url"], passage["url"])
                self.assertEqual(result["source_s"], passage["source_s"])
                self.assertLess(*result["source_s"])
                for field in ("name", "relation", "anchor", "motion", "transfer", "limitation"):
                    self.assertTrue(result[field], field)
                self.assertEqual(find_direction("", key)[0], result)

    def test_structural_briefs_in_new_domains_select_the_additional_passages(self):
        briefs = {
            "recursive-spatial-partition":("Subdividir la finca en cuadrantes", "Subdivide the plot into quadrants"),
            "item-reassignment":("Reasignar pedidos entre muelles", "Reassign orders between depots"),
            "qualitative-tradeoff":("Disyuntiva entre coste y calidad al comprar", "Weigh quality against cost in catering"),
            "time-series-reveal":("Cuándo llegó el pico de demanda por hora", "When did visits peak during the day?"),
            "ordered-segmentation":("Trocear una grabación de campo en tramos ordenados", "Split a recording into successive clips"),
            "stacked-category-comparison":("Aportes de cada producto por región", "A breakdown of wages and tips by location"),
            "selected-route":("Qué ruta fue elegida entre las alternativas", "Which route was chosen through the museum?"),
            "lane-handoff":("Relevo entre los equipos de limpieza", "Trace the handoff between museum teams"),
            "mirrored-transformation":("Conversión y recuperación del original", "An encoding and decoding round-trip"),
            "context-focus-return":("Acercarse al resultado y volver al mapa", "Zoom into the completed wing then return to the plan"),
            "context-detail":("Ampliar la subregión al lado del mapa original", "Place a detail inset beside the map"),
            "containment":("Agrupar las personas por departamento", "Group the volunteers into departments"),
            "paired-comparison":("Comparar dos métodos de entrega de material", "Compare two ways of delivering tickets"),
            "ordered-cards":("Explicación breve para cada etapa de estreno", "Explain each stage of restoring a print"),
            "progressive-table":("Primer nivel de precio que cumple el umbral", "Show the first size that meets the threshold"),
            "merge-lineage":("Reconciliar dos versiones del manuscrito", "Merge two edits of a manuscript"),
            "partition-sequence":("Dividir las pistas de audio en los mismos cortes", "Mark boundaries across the two tracks"),
            "repeated-event":("La última lectura periódica del sensor", "The latest periodic sensor reading"),
            "count-threshold":("Conteo de visitantes por hora frente al límite de aforo", "Count arrivals per hour against capacity"),
            "paired-criteria":("Igualdad por identificador y por contenido", "Compare equality by ID and by content"),
        }
        self.assertEqual(set(briefs), {key for key in RULES if not key.startswith("video-")})
        for relation, phrases in briefs.items():
            for brief in phrases:
                with self.subTest(brief=brief):
                    selected = find_direction(brief)
                    self.assertTrue(selected)
                    self.assertEqual(selected[0]["source_s"], evidence_for(relation)["source_s"])
                    self.assertEqual(selected[0]["video_id"], evidence_for(relation)["video_id"])

    def test_type_of_validated_relation_narrows_the_references(self):
        expected = {"hierarchy","fan-out","fan-in","exchange","sequence","comparison","group-members","parallel-states"}
        self.assertEqual(set(expected), set(FAMILY_EXAMPLES))
        for family in expected:
            default = find_direction("", family)[0]
            source = evidence_for(FAMILY_EXAMPLES[family])
            self.assertEqual((default["url"], default["source_s"]), (source["url"], source["source_s"]))
        numeric = find_direction("Cuál sede vendió más entradas", "comparison")[0]
        self.assertEqual(numeric["video_id"],passages()["stacked-category-comparison"][0])
        self.assertIn("solo si existen componentes",numeric["transfer"])
        self.assertEqual(find_direction("merge revisions of a field report", "fan-in")[0]["relation"], "merge-lineage")
        self.assertNotEqual(find_direction("merge revisions of a field report", "fan-out")[0]["relation"], "merge-lineage")

    def test_related_directions_are_bounded_and_unsupported_briefs_abstain(self):
        brief = "Agrupar por departamentos y recorrer la ruta elegida al reconciliar dos versiones"
        selected = find_direction(brief)
        self.assertGreaterEqual(len(selected),2)
        self.assertLessEqual(len(selected),3)
        self.assertEqual(len(selected),len({item["relation"] for item in selected}))
        for brief in ("", "Mostrar los datos de una ciudad", "Proceso", "Room", "Prioridades", "Bus", "Tabla",
                      "Una explicación sobre museos", "A map", "Balancear costos", "Make it look professional"):
            with self.subTest(brief=brief):
                self.assertEqual(find_direction(brief), [])


if __name__ == "__main__":
    unittest.main()
