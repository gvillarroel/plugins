"""Check semantic suggestions, data ambiguity, catalogue ownership and CLI failures."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from motion_recipe import DIAGRAM_KINDS, FIELDS
from recommend_motion import CHOICES, ROOT, SYSTEM_INPUTS, profile_rows, read_records, recommend


class MotionSuggestions(unittest.TestCase):
    def test_cli_exposes_a_clear_reference_and_requests_its_actual_fields(self):
        script = ROOT / "scripts" / "recommend_motion.py"
        brief = "Qué ruta fue elegida entre los itinerarios alternativos de un museo"
        args = [sys.executable, "-B", "-X", "utf8", str(script), "--brief", brief]
        def run(*extra):
            return subprocess.run([*args, *extra], encoding="utf-8", check=True, capture_output=True).stdout

        result = json.loads(run("--json"))
        self.assertEqual(result["decision"], "insufficient")
        self.assertIsNone(result["recommendation"])
        direction, = result["study_directions"]
        self.assertEqual(direction["relation"], "selected-route")
        self.assertIn("ramas permitidas", result["question"])
        self.assertIn("destino", result["question"])
        output = run()
        for field in ("name", "transfer", "url"):
            self.assertIn(direction[field], output)
        self.assertIn(result["question"], output)

    def test_cli_does_not_present_a_reference_as_the_choice_for_an_ambiguous_brief(self):
        script = ROOT / "scripts" / "recommend_motion.py"
        brief = "Quiero ver la tendencia mensual y comparar ventas por región"
        result = recommend(brief, rows=[
            {"fecha": "2025-01", "región":"Norte", "ventas": 20},
            {"fecha": "2025-02", "región":"Sur", "ventas": 30},
        ])
        self.assertEqual(result["decision"], "ambiguous")
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "data.csv"
            data.write_text("fecha,región,ventas\n2025-01,Norte,20\n2025-02,Sur,30\n",encoding="utf-8")
            output = subprocess.run([sys.executable,"-B","-X","utf8",str(script),"--brief",brief,"--data",str(data)],
                                    encoding="utf-8",check=True,capture_output=True).stdout
        self.assertNotIn(result["study_directions"][0]["transfer"], output)

    def test_bilingual_concept_cues_reach_the_real_diagram(self):
        examples = {
            "field-packing": ("Empaquetar cuatro campos en memoria", "Show the fields packed into a buffer"),
            "layer-preview": ("Cada capa modifica la imagen", "Each layer changes the preview"),
            "isometric-layers": ("Separar la pieza superior de una pila", "Lift one block out of the stack"),
            "pass-strip": ("Varias etapas construyen un único envío", "Ordered operations produce a single output"),
            "module-transfer": ("Sacar una fila del inventario para inspeccionarla en detalle", "Inspect one row from the inventory"),
            "vertex-remap": ("Los vértices de la retícula forman una superficie", "Map a grid of points onto a surface"),
            "import-footprint": ("Qué grupos se solapan dentro de un mismo total", "Find overlapping subsets in the bundle"),
            "command-lanes": ("Comparar duración de cuatro llamadas GPU", "Compare the duration of GPU commands"),
            "shared-host": ("Dos clientes comparten una escena", "Two hosts use the same scene"),
            "split-clock": ("Dos relojes: el worker se retrasa", "Compare two clocks when a thread overruns its slot"),
        }
        mathematics = {
            "pivot-rotation": ("El brazo gira alrededor del pivote","Rotate a marked point about a fixed pivot"),
            "object-route": ("Seguir el objeto por las estaciones", "Follow the token as it returns to its first stop"),
            "rigid-rearrangement": ("Reordenar los rectángulos conservando el área", "Rearrange rectangular tiles of equal area"),
            "contact-transfer": ("Al presionar queda una huella", "The press leaves an imprint"),
            "interval-refinement": ("Acotar intervalos anidados", "Narrow the nested intervals"),
            "trajectory-trace": ("La trayectoria del móvil y su gráfica", "Plot the trajectory against its trace"),
        }
        self.assertEqual(set(examples) | set(mathematics) | set(SYSTEM_INPUTS), set(DIAGRAM_KINDS))
        for artifact, phrases in mathematics.items():
            for brief in phrases:
                with self.subTest(brief=brief):
                    item = recommend(brief)["recommendation"]
                    self.assertEqual(item["id"], artifact)
                    self.assertIn("youtube.com/watch?v=", item["source"])
        for artifact, phrases in examples.items():
            for phrase in phrases:
                with self.subTest(artifact=artifact, phrase=phrase):
                    result = recommend(phrase)
                    self.assertEqual(result["decision"], "recommended")
                    item = result["recommendation"]
                    self.assertEqual(item["id"], artifact)
                    self.assertEqual(item["kind"], "artifact")
                    self.assertIn("S64kbVjlbpU&t=", item["source"])
                    self.assertTrue(item["anchor"] and item["motion"] and item["why"])

    def test_system_design_concepts_in_both_languages(self):
        examples = {
            "ring-handoff": ("Qué claves reasigna el anillo cuando entra un nodo", "Which key changes owner on the hash ring?"),
            "bit-probe": ("Consultar la pertenencia con un filtro de Bloom", "Probe a Bloom filter and check the bits"),
            "message-ladder": ("Intercambio de mensajes entre cliente y servidor", "Show a request and its reply",
                               "¿Quién envía cada mensaje entre el cliente y el servidor?",
                               "Who sends each message between the client and the server?"),
            "detail-callout": ("Ampliar los fragmentos de una dirección", "Zoom into the parts of a URL"),
            "radix-ladder": ("Convertir un entero a base 62 y leer los restos", "Use remainders to encode an integer in base 16"),
            "token-gate": ("Una ficha se consume al admitir la solicitud", "Reject a request when the token bucket is empty"),
            "resolution-fan": ("Generar versiones de distinta resolución", "Produce several resolution variants from one clip"),
            "queue-router": ("Clasificar trabajos en colas de prioridad", "Dispatch tasks from priority queues"),
            "staged-network": ("Seguir paso a paso la ruta entre los nodos", "Introduce architecture components in stages"),
        }
        self.assertEqual(set(examples), set(SYSTEM_INPUTS))
        for target, phrases in examples.items():
            for phrase in phrases:
                with self.subTest(target=target, phrase=phrase):
                    result = recommend(phrase)
                    self.assertEqual(result["decision"], "recommended", result)
                    item = result["recommendation"]
                    self.assertEqual((item["kind"], item["id"]), ("artifact", target))
                    expected_page = "youtube.com/playlist?list=" if target == "staged-network" else "youtube.com/watch?v="
                    self.assertIn(expected_page, item["source"])
                    self.assertNotIn("S64kbVjlbpU", item["source"])
                    self.assertTrue(item["anchor"] and item["motion"] and item["next_step"])

    def test_staged_recipes_match_relations_in_both_languages(self):
        examples = {
            1: ("Rutas del balanceador a réplicas de lectura y primaria de escritura",
                "Read replicas and primary writes behind the load balancer"),
            4: ("¿Cuántos servidores necesito dada la capacidad por servidor?",
                "How many servers at this capacity per server?"),
            5: ("Una emisión produce versiones de distinta resolución para cuatro pantallas",
                "Stream renditions are distributed to different devices"),
            6: ("Las tres rondas de una entrevista técnica", "Use a card for each of three onsite interview rounds"),
            7: ("Conectar tres clientes al servidor de chat", "Three clients connect to a chat server"),
            8: ("Tres hilos de un proceso comparten memoria", "Threads share the heap inside a process"),
            11: ("Construir un árbol de prefijos", "Walk down the branches of a prefix tree"),
            12: ("Tres productores envían al bus de eventos", "An event bus for publishers and subscribers"),
            13: ("Disponer los hitos por fecha en una línea de tiempo", "Place milestones on a chronological timeline"),
            14: ("Una categoría agrupa tres recursos", "One parent category contains three resources"),
            16: ("El hash de la clave y el módulo seleccionan una partición", "Use the key hash modulo the number of shards"),
            18: ("Fan-out de chat", "Broadcast one message to many recipients",
                 "Mostrar cómo recibe un grupo de chat el mensaje de una persona",
                 "Una persona envía un mensaje al grupo de chat",
                 "Show how a group chat receives a message from one person",
                 "One member sends a message to the group chat"),
        }
        corpus = json.loads((ROOT / "references/bytebytego-corpus.json").read_text(encoding="utf-8"))
        cases = {s["index"]: s for s in corpus["videos"] if s["artifact"] == "staged-network"}
        self.assertEqual(examples.keys(), cases.keys())
        for index, phrases in examples.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    result = recommend(phrase)
                    self.assertEqual(result["decision"], "recommended", result)
                    selected = result["recommendation"]
                    case = cases[index]
                    self.assertEqual(selected["id"], "staged-network")
                    self.assertEqual(selected["scene_id"], case["scene"])
                    self.assertEqual(selected["source"], case["url"])
                    self.assertEqual(selected["source_s"], case["source_s"])
                    self.assertEqual(selected["anchor"], case["anchor"])
                    self.assertIn("init " + case["scene"], selected["next_step"])
                    recipe = json.loads((ROOT / selected["recipe"]).read_text(encoding="utf-8"))
                    scene = next(s for s in recipe["scenes"] if s["id"] == selected["scene_id"])
                    self.assertEqual(scene["artifact"], selected["id"])

    def test_specific_layouts_keep_ambiguity_and_generic_fallback(self):
        mixed = recommend("Mostrar un bus de eventos y cómo tres hilos comparten el heap.")
        self.assertEqual(mixed["decision"], "ambiguous")
        self.assertIsNone(mixed["recommendation"])
        self.assertEqual({c["scene_id"] for c in mixed["alternatives"]},
                         {"video-08-staged-network", "video-12-staged-network"})
        for phrase in ("Show the architecture in stages", "Introducir la arquitectura por etapas"):
            generic = recommend(phrase)["recommendation"]
            self.assertEqual(generic["id"], "staged-network")
            self.assertNotIn("scene_id", generic)
            self.assertIn("youtube.com/playlist?list=", generic["source"])
        self.assertIsNone(recommend("Una arquitectura")["recommendation"])
        for inverse in ("El grupo de chat envía un mensaje a una única persona",
                        "The group chat sends a message to one person"):
            self.assertIsNone(recommend(inverse)["recommendation"])
        static = recommend("Árbol de prefijos sin animación")["recommendation"]
        self.assertEqual(static["kind"], "static")
        self.assertNotIn("scene_id", static)
        self.assertEqual(recommend("Latency trend over time for the event bus")["recommendation"]["id"], "time-series")

    def test_system_mechanism_and_observed_metrics_are_different_questions(self):
        log = [{"orden": 1, "emisor": "A", "receptor": "B", "mensaje": "pregunta", "latencia": 7},
               {"orden": 2, "emisor": "B", "receptor": "A", "mensaje": "respuesta", "latencia": 3}]
        self.assertEqual(recommend("El intercambio de mensajes entre cliente y servidor", log)["recommendation"]["id"], "message-ladder")
        self.assertEqual(recommend("Comparar la latencia del intercambio de mensajes por emisor", log)["recommendation"]["id"], "data-chart")
        self.assertEqual(recommend("Latency trend over time for a request and its response", log)["recommendation"]["id"], "time-series")
        self.assertEqual(recommend("Histograma de latencia de las colas de prioridad", log)["recommendation"]["id"], "distribution")
        self.assertEqual(recommend("Valor medido de latencia de una consulta de Bloom")["recommendation"]["kind"], "static")
        self.assertEqual(recommend("Anillo de claves sin animación", log)["recommendation"]["kind"], "static")
        self.assertEqual(recommend("Show how the token bucket refills over time")["recommendation"]["id"], "token-gate")
        self.assertEqual(recommend("Diagrama de flujo que revela los nodos paso a paso")["recommendation"]["id"], "staged-network")
        for phrase in ("servidor", "tokens", "clientes", "arquitectura", "priority", "resolución", "bits", "código"):
            self.assertEqual(recommend(phrase)["decision"], "insufficient", phrase)
        operands = [{"value": 21, "base": 16}, {"value": 4, "base": 2}]
        self.assertEqual(recommend("Convertir el valor a base 16", operands)["recommendation"]["id"], "radix-ladder")

    def test_ordered_bidirectional_events_and_generic_edge_lists(self):
        rows = [{"order": 2, "from": "B", "to": "A", "message": "Reply"},
                {"order": 1, "from": "A", "to": "B", "message": "Request"}]
        self.assertEqual(recommend(rows=rows)["recommendation"]["id"], "message-ladder")
        # Endpoints alone do not identify a timed exchange or measure duration.
        self.assertEqual(recommend(rows=[{"origen": 1, "destino": 2}, {"origen": 2, "destino": 3}])["recommendation"]["id"], "node-link")
        for field, value in (("order", 2), ("from", "C"), ("message", "")):
            with self.subTest(field=field):
                self.assertEqual(recommend(rows=[rows[0], {**rows[1], field:value}])["recommendation"]["id"], "node-link")
        self.assertEqual(recommend(rows=[{"from": "A", "to": None}, {"from": "B", "to": "C"}])["decision"], "insufficient")

    def test_every_intent_has_an_existing_owner(self):
        for intent in CHOICES:
            with self.subTest(intent=intent):
                item = recommend(intent=intent)["recommendation"]
                if item["kind"] == "artifact":
                    self.assertIn(item["id"], FIELDS)
                    self.assertTrue(item["source"].startswith("https://"))
                else:
                    self.assertTrue((ROOT / item["source"]).is_file(), item["source"])

    def test_data_shape_suggests_without_inventing_intent_or_values(self):
        # The numbers happen to sum to 100. No composition is stated.
        rows = [{"SKU": "08001", "región": "Norte", "unidades": 38},
                {"SKU": "08002", "región": "Sur", "unidades": 62}]
        result = recommend(rows=rows)
        self.assertEqual(result["recommendation"]["id"], "data-chart")
        self.assertEqual(result["data_profile"]["identifiers"], ["SKU"])
        self.assertTrue(result["question"])
        self.assertEqual(recommend(rows=[{"valor": 38}, {"valor": 62}])["decision"], "insufficient")

    def test_same_data_supports_different_questions(self):
        rows = [{"fecha": "2025-01", "región": "Norte", "ingresos": 40},
                {"fecha": "2025-03", "región": "Sur", "ingresos": 60}]
        result = recommend(rows=rows)
        self.assertEqual(result["decision"], "ambiguous")
        self.assertIsNone(result["recommendation"])
        self.assertEqual({item["id"] for item in result["alternatives"]}, {"time-series", "data-chart"})
        self.assertEqual(recommend("La evolución de ingresos", rows)["recommendation"]["producer"], "line-world-d3")
        self.assertEqual(recommend("Comparar ventas por región", rows)["recommendation"]["id"], "data-chart")
        self.assertEqual(recommend("Consultar valores exactos", rows)["recommendation"]["kind"], "static")

    def test_time_is_unambiguous_and_reading_holds_take_precedence(self):
        rows = [{"año": 2024, "valor": 45}, {"año": 2025, "valor": 55}]
        self.assertEqual(recommend(rows=rows)["recommendation"]["id"], "time-series")
        self.assertEqual(recommend("Mostrar tendencia sin animación", rows, "trend")["recommendation"]["kind"], "static")

    def test_denominator_and_membership_are_different_relationships(self):
        self.assertEqual(recommend("La proporción del total")["recommendation"]["id"], "chart-ring")
        self.assertEqual(recommend("Cómo se reparte el presupuesto")["recommendation"]["id"], "part-to-whole")
        rows = [{"grupo": "A", "porcentaje": "20%", "denominador": 100},
                {"grupo": "B", "porcentaje": "25%", "denominador": 400}]
        result = recommend(rows=rows, intent="share")
        self.assertEqual(result["decision"], "insufficient")
        self.assertIn("denominadores", result["question"])
        self.assertEqual(result["data_profile"]["percentages"], ["porcentaje"])
        self.assertEqual(recommend("Comparar los porcentajes por grupo", rows)["recommendation"]["id"], "data-chart")
        self.assertEqual(recommend("La proporción del total con distintos denominadores")["decision"], "insufficient")

    def test_ambiguity_never_breaks_ties_by_catalog_order(self):
        result = recommend("Un campo se empaqueta en memoria y una fila se abre en detalle")
        self.assertEqual(result["decision"], "ambiguous")
        self.assertEqual({item["id"] for item in result["alternatives"]}, {"field-packing", "module-transfer"})
        self.assertIsNone(result["recommendation"])
        for phrase in ["GPU", "módulos", "animación elegante", "población de la región", "35 %", "alcanzó un 140 %"]:
            self.assertEqual(recommend(phrase)["decision"], "insufficient", phrase)

    def test_categories_need_two_distinct_observed_groups_for_the_same_measure(self):
        rows = [{"biblioteca": "Centro", "visitas": 105, "aforo": 50},
                {"biblioteca": "Ribera", "visitas": "pendiente", "aforo": 80}]
        question = "Compara las visitas por biblioteca en abril"
        for insufficient in [rows, [*rows, {"biblioteca": "Centro", "visitas": 109}]]:
            report = recommend(question, insufficient)
            self.assertEqual(report["decision"], "insufficient")
            self.assertIsNone(report["recommendation"])
            self.assertEqual(report["alternatives"][0]["id"], "static-comparison")
            self.assertIn("tabla provisional", report["question"])
        enough = recommend(question, [*rows, {"biblioteca": "Norte", "visitas": 0}])
        self.assertEqual(enough["recommendation"]["id"], "data-chart")
        self.assertIn("visitas", enough["question"])

    def test_natural_rank_filter_lookup_and_evolution(self):
        rows = [{"mes": "2025-01", "sucursal": "Norte", "importe": 60},
                {"mes": "2025-02", "sucursal": "Sur", "importe": 80}]
        cases = {"¿Dónde se vendió más en febrero?": "data-chart",
                 "Ventas por sucursal en febrero": "data-chart",
                 "¿Cuánto vendió Norte en enero?": "static-comparison",
                 "La cifra exacta de Norte en enero": "static-comparison",
                 "Cómo cambian los ingresos de enero a junio": "time-series"}
        for brief, target in cases.items():
            with self.subTest(brief=brief):
                self.assertEqual(recommend(brief, rows)["recommendation"]["id"], target)
        self.assertEqual(recommend("¿Cómo varía el importe con el tiempo?")["recommendation"]["id"], "time-series")
        self.assertEqual(recommend("Cómo evoluciona la lámina cuando se dobla. No hay medidas.")["decision"], "insufficient")
        self.assertEqual(recommend("La fila sale de la lista para inspeccionarla")["recommendation"]["id"], "module-transfer")

    def test_real_observations_use_data_scale_instead_of_fixed_lane_demo(self):
        rows = [{"llamada": "bloom", "duracion_ms": 1.7}, {"llamada": "lighting", "duracion_ms": 23.4}]
        item = recommend("Comparar la duración de dos llamadas GPU", rows)["recommendation"]
        self.assertEqual((item["kind"], item["producer"]), ("specialist", "line-world-d3"))
        self.assertEqual((item["reference_artifact"], item["fit"]), ("command-lanes", "data-driven-adaptation"))
        self.assertIn("proporciones fijas", item["next_step"])
        for brief in ("Cuánto duró cada llamada en milisegundos", "How many milliseconds did each call take?",
                      "How long each call lasted in ms"):
            with self.subTest(brief=brief):
                item = recommend(brief)["recommendation"]
                self.assertEqual((item["producer"], item["reference_artifact"]),
                                 ("line-world-d3", "command-lanes"))
        clock = recommend(intent="compare-clocks")["recommendation"]
        self.assertIn("ocho pulsos", clock["next_step"])
        for key in ("ordered-passes", "preview-layers", "shared-resource"):
            item = recommend(intent=key)["recommendation"]
            self.assertIn("adapta el dibujo", item["next_step"])

    def test_before_after_validity_and_dependency_wording(self):
        item = recommend("Cómo cambió el tiempo de espera antes y después del rediseño")
        self.assertEqual(item["recommendation"]["producer"], "line-world-motion-direction")
        self.assertIn("unidad", item["question"])
        self.assertEqual(recommend("El aspecto de la sala antes y después")["decision"], "ambiguous")
        bad = [{"valor": 10, "unidad": "s"}, {"valor": 25, "unidad": "%"}]
        self.assertEqual(recommend(rows=bad, intent="paired-change")["decision"], "insufficient")
        dep = recommend("Qué operaciones corren en paralelo y cuáles dependen de otras")
        self.assertEqual(dep["recommendation"]["producer"], "line-world-mermaid")

    def test_profile_preserves_gaps_and_does_not_call_identifiers_dates(self):
        p = profile_rows([{"fecha": "2025-01", "ID": "2025-02", "medida": "0"},
                          {"fecha": "2025-04", "ID": "2025-05", "medida": None}])
        self.assertEqual(p["missing"], {"medida": 1})
        self.assertEqual(p["measures"], ["medida"])
        self.assertEqual(p["dates"], ["fecha"])

    def test_spanish_decimal_and_out_of_range_share(self):
        rows = [{"precio": "2,5", "cuota": "12,5%"}, {"precio": "14,75", "cuota": "135,4%"}]
        profile = profile_rows(rows)
        self.assertEqual(profile["measures"], ["precio", "cuota"])
        self.assertEqual(profile["out_of_range_percentages"], ["cuota"])
        self.assertEqual(recommend(intent="share", rows=rows)["decision"], "insufficient")
        self.assertEqual(recommend("El porcentaje del total es -7,2 %")["decision"], "insufficient")

    def test_cli_reads_csv_and_json_and_fails_for_malformed_tables(self):
        script = Path(__file__).with_name("recommend_motion.py")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            for suffix, content in [("csv", "fecha;valor\n2025-01;40\n2025-02;60\n"),
                                    ("json", '[{"fecha":"2025-01","valor":40},{"fecha":"2025-02","valor":60}]')]:
                path = directory / ("tabla." + suffix)
                path.write_text(content, encoding="utf-8-sig")
                proc = subprocess.run([sys.executable, "-X", "utf8", str(script), "--data", str(path), "--json"],
                                      encoding="utf-8", check=True, capture_output=True)
                self.assertEqual(json.loads(proc.stdout)["recommendation"]["id"], "time-series")
            for suffix, content in [("json", '{"filas":[]}'), ("csv", "a,a\n1,2\n"),
                                    ("json", '[{"valor":[12]}]'), ("csv","a,b\n1,2,3\n")]:
                path = directory / ("invalid." + suffix)
                path.write_text(content, encoding="utf-8")
                with self.subTest(suffix=suffix, content=content), self.assertRaises(ValueError):
                    read_records(path)


if __name__ == "__main__":
    unittest.main()
