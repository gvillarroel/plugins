from pathlib import Path
import json
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import brief_to_video as brief
import audit_comparisons
import narrated


EXAMPLES=Path(__file__).resolve().parents[1]/"assets"


class BriefTests(unittest.TestCase):
    def test_phone_comparison_keeps_values_above_full_width_bars_and_space_for_captions(self):
        sample = brief.load(EXAMPLES / "recorrido-brief.json")
        visual, _ = brief.compile_brief(sample, [390, 844])
        im, _, _ = brief.direction.frame(visual, visual["scenes"][1], 0)
        first, second = im.info["comparisonRows"]
        self.assertGreaterEqual(first["end"] - first["zero"], im.width * .85)
        self.assertAlmostEqual((second["end"] - second["zero"]) / (first["end"] - first["zero"]), 12 / 18)
        for row in (first, second):
            name, value = row["labelBox"], row["valueBox"]
            self.assertLess(name[2], value[0])
            self.assertGreaterEqual(value[3] - value[1], 20)
            self.assertLess(max(name[3], value[3]) + 10, row["y"])
        self.assertLess(first["y"], second["labelBox"][1])
        self.assertLess(second["y"], im.info["sourceBox"][1])
        self.assertLess(im.info["sourceBox"][3], im.height * .72)

        horizontal, _ = brief.compile_brief(sample, [960, 540])
        self.assertNotIn("layout", horizontal)

    def test_phone_header_preserves_an_explicit_subject_label(self):
        sample = brief.load(EXAMPLES / "recorrido-brief.json")
        del sample["subjectLabel"]
        def header(source):
            visual, _ = brief.compile_brief(source, [390, 844])
            return brief.direction.frame(visual, visual["scenes"][0], 0)[2]
        implicit = header(sample)
        explicit = header({**sample, "subjectLabel": "Comparación"})
        self.assertNotEqual(implicit, explicit)
        self.assertNotEqual(explicit, header({**sample, "subjectLabel": "Destino"}))
        self.assertNotEqual(implicit, header({**sample, "subject": "Otro recorrido"}))

    def test_data_only_brief_derives_direction_and_percentage_points(self):
        sample = brief.load(EXAMPLES / "tasa-brief.json")
        for kind in brief.SIZES:
            checked = brief.validate_brief(EXAMPLES / "tasa-brief.json", kind)
            self.assertIn("5,15 por ciento", checked["scenes"][0]["speech"])
            self.assertIn("0,23 puntos porcentuales menos", checked["scenes"][1]["speech"])
            self.assertIn("0,23 puntos porcentuales", checked["scenes"][1]["title"])
        for first, second, expected in ((0,1,"1 punto porcentual más"), (0,-1,"1 punto porcentual menos"),
                                       (5,5,"el mismo valor"),(-2,-.5,"1,5 puntos porcentuales más")):
            sample["measures"][0]["value"] = first
            sample["measures"][1]["value"] = second
            _, speech = brief.compile_brief(sample, brief.SIZES["vertical"])
            self.assertIn(expected, speech[1])
            self.assertNotIn("punto porcentuals", speech[1])
        sample["recordings"]=["first.wav","second.wav"]
        with self.assertRaisesRegex(ValueError, "palabras grabadas"):
            brief.compile_brief(sample, brief.SIZES["vertical"])

    def test_crossing_zero_speaks_the_sign_and_keeps_each_measure_readable(self):
        sample = brief.load(EXAMPLES / "recorrido-brief.json")
        sample.update(title="De {a} a {b}", spokenUnit="grados Celsius",
                      narration=["El congelador pasó de más {a} a {b}.", "La temperatura bajó {gap}."],
                      measures=[{"value": 4, "label": "Al inicio", "unit": "°C"},
                                {"value": -6, "label": "Al final", "unit": "°C"}])
        visual, speech = brief.compile_brief(sample, [390, 844])
        self.assertEqual(visual["scenes"][0]["title"], "De 4 °C a -6 °C")
        self.assertIn("menos 6 grados Celsius", speech[0])
        self.assertEqual(speech[1], "La temperatura bajó 10 grados Celsius.")
        chunks = brief.caption_blocks(speech[0], 32, "grados Celsius")
        self.assertEqual(" ".join(" ".join(chunks).split()), speech[0])
        self.assertTrue(all(len(block.split()) >= 4 for block in chunks))
        self.assertTrue(all("Celsius" != line.strip(".") for block in chunks for line in block.splitlines()))
        self.assertTrue(all(len(block.splitlines()) <= 2 and max(map(len, block.splitlines())) <= 32 for block in chunks))
        self.assertTrue(any("menos 6 grados Celsius" in block for block in chunks))
        scene = visual["scenes"][0]
        reading, _, _ = brief.direction.frame(visual, scene, scene["cue"] + scene["move"])
        left, top, right, bottom = reading.info["zeroLabelBox"]
        self.assertGreaterEqual(bottom - top, 12)
        self.assertEqual(brief.direction.number(-0.0), "0")

    def test_preflight_prints_final_spoken_numbers_without_output_or_media_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            sample = Path(temp) / "jarras.json"
            sample.write_bytes((EXAMPLES / "jarras-brief.json").read_bytes())
            run = subprocess.run(
                [sys.executable, "-B", brief.__file__, str(sample), "--validate-only", "--format", "vertical"],
                capture_output=True, env={**brief.os.environ, "PATH": "", "PYTHONIOENCODING": "cp1252"},
                check=True,
            )
            result = json.loads(run.stdout.decode("utf-8"))
            self.assertEqual(result["size"], [390, 844])
            self.assertEqual(result["sourceCaption"], "Datos simulados · Volúmenes de ejemplo")
            self.assertIn("1,2 litros", result["scenes"][0]["speech"])
            self.assertEqual(" ".join(" ".join(result["scenes"][0]["captionBlocks"]).split()),result["scenes"][0]["speech"])
            self.assertEqual(result["scenes"][1]["title"], "La jarra grande tiene 0,6 L más")
            self.assertEqual(list(Path(temp).iterdir()), [sample])

    def test_voice_runner_respects_user_network_choice_and_script_python_range(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(brief.importlib.util, "find_spec", return_value=None), \
                 patch.object(brief.shutil, "which", return_value="uv"), \
                 patch.object(brief, "media_command") as invoke:
                for offline in (False, True):
                    brief.make_audio({"scenes": [{"text": "Hola"}]}, root / "audio.json", root / "voz", offline=offline)
                    command = invoke.call_args.args[0]
                    self.assertEqual(command[0:2], ["uv", "run"])
                    self.assertEqual(command.count("--offline"), 2 if offline else 0)
                    self.assertEqual("--no-python-downloads" in command, offline)
                    self.assertNotIn("--python", command)
                    self.assertNotIn("--model", command)

    def test_recordings_skip_voice_dependencies_and_explicit_models_are_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(brief.importlib.util, "find_spec", side_effect=AssertionError), \
                 patch.object(brief, "media_command") as invoke:
                brief.make_audio({"scenes": [{"file": "voz.wav"}]}, root / "audio.json", root / "voz")
                self.assertEqual(invoke.call_args.args[0][0], sys.executable)
                with self.assertRaisesRegex(ValueError, "onnx.json"):
                    brief.make_audio({"scenes": [{"text": "Hola"}]}, root / "audio.json", root / "voz", root / "ausente.onnx")

    def test_exact_decimal_delta_and_spoken_unit(self):
        raw=brief.load(EXAMPLES/"jarras-brief.json")
        visual,voice=brief.compile_brief(raw,brief.SIZES["vertical"])
        self.assertEqual(visual["scenes"][1]["title"],"La jarra grande tiene 0,6 L más")
        self.assertIn("0,6 litros",voice[0])
        self.assertIn("1,2 litros",voice[0])
        self.assertTrue(visual["sourceCaption"].startswith("Datos simulados"))

    def test_comparison_inflects_rows_speech_difference_and_caption_groups(self):
        specimen = brief.load(EXAMPLES / "tasa-brief.json")
        for first, second, unit, voice_unit, rows, gap in [
            (1, 2, "euros", "euros", ["1 euro", "2 euros"], "1 euro más"),
            (1, 2, "litro", "litro", ["1 litro", "2 litros"], "1 litro más"),
            (2, 1, "min", "minutos", ["2 min", "1 min"], "1 minuto menos"),
            (2, 1, "ms", "milisegundos", ["2 ms", "1 ms"], "1 milisegundo menos"),
            (-1, -2, "°C", "grados Celsius", ["-1 °C", "-2 °C"], "1 grado Celsius menos"),
            (3.001, 3.002, "%", "por ciento", ["3,001 %", "3,002 %"], "0,001 puntos porcentuales más"),
            (-.005, -.004, "°C", "grados Celsius", ["-0,005 °C", "-0,004 °C"], "0,001 grados Celsius más"),
            (-0.0, 0, "€", "euros", ["0 €", "0 €"], "el mismo valor"),
        ]:
            specimen["measures"] = [{"label": label, "unit": unit, "value": value}
                                    for label, value in (("Primera", first), ("Segunda", second))]
            specimen["spokenUnit"] = voice_unit
            for size in brief.SIZES.values():
                with self.subTest(unit=unit, first=first, size=size):
                    visual, voice = brief.compile_brief(specimen, size)
                    self.assertIn(gap, voice[1])
                    scene = visual["scenes"][1]
                    frame = brief.direction.frame(visual, scene, scene["cue"] + scene["move"])[0]
                    self.assertEqual([row["displayed"] for row in frame.info["comparisonRows"]], rows)
                    units = brief.spoken_units(specimen)
                    singular = brief.direction.unit_for(1, voice_unit)
                    wrapped = brief.caption_blocks("La medida fue 1 " + singular + " en total.", 16, units)
                    self.assertTrue(any("1 " + singular in line for block in wrapped for line in block.splitlines()))

    def test_simulation_credit_uses_the_source_detail_once(self):
        sample = brief.load(EXAMPLES / "recorrido-brief.json")
        for detail, expected in (
            ("Datos simulados", "Datos simulados"),
            ("Datos simulados del viaje", "Datos simulados del viaje"),
            ("Recorridos de ejemplo", "Datos simulados · Recorridos de ejemplo"),
        ):
            with self.subTest(detail=detail):
                sample["source"]["detail"] = detail
                visual, _ = brief.compile_brief(sample, brief.SIZES["vertical"])
                self.assertEqual(visual["sourceCaption"], expected)

    def test_audit_accepts_a_difference_of_one_in_both_layouts(self):
        sample = audit_comparisons.sample(random.Random(12), 0)
        sample["spokenUnit"] = "centímetros"
        for row, value in zip(sample["measures"], (1.59, 0.59)):
            row.update(value=value, unit="cm")
        for kind in brief.SIZES:
            with self.subTest(layout=kind):
                self.assertLessEqual(audit_comparisons.inspect(sample, kind), 2)

    def test_decimal_tokens_cannot_turn_distinct_measurements_into_an_equal_pair(self):
        raw = json.dumps(brief.load(EXAMPLES / "tasa-brief.json"), ensure_ascii=False)
        raw = raw.replace("5.15", "1.00000000000000001").replace("4.92", "1.00000000000000002")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "distintos.json"
            path.write_text(raw, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "1.00000000000000001 pierde precisión"):
                brief.validate_brief(path, "vertical")
            path.write_text(raw.replace("1.00000000000000001", "1.000").replace("1.00000000000000002", "1.00"),
                            encoding="utf-8")
            self.assertIn("el mismo valor", brief.validate_brief(path, "vertical")["scenes"][1]["speech"])

    def test_units_source_fields_and_voice_binding(self):
        for field in ("unit","source","bound","label","finite"):
            with self.subTest(field=field):
                raw=brief.load(EXAMPLES/"recorrido-brief.json")
                if field=="unit":raw["measures"][0]["unit"]="s"
                if field=="source":raw["source"]["type"]="observed"
                if field=="bound":raw["narration"][0]="Ambas rutas duran veinte minutos."
                if field=="label":raw["measures"][1]["label"]=raw["measures"][0]["label"]
                if field=="finite":raw["measures"][1]["value"]=float("nan")
                with self.assertRaises(ValueError):brief.compile_brief(raw,[390,844])

    def test_reading_scene_holds_the_same_bars_and_roles(self):
        v,_=brief.compile_brief(brief.load(EXAMPLES/"recorrido-brief.json"),[390,844])
        data={"sample_rate":48000,"master":{"samples":288000},"scenes":[
            {"id":name,"start_sample":begin,"end_sample":begin+144000,
             "sentences":[{"absolute_start_sample":begin+12000,"absolute_end_sample":begin+104000}]}
            for name,begin in (("medidas",0),("lectura",144000))]}
        frames,positions=narrated.clock(v,data)
        score=narrated.score(v,data,frames,positions)
        self.assertEqual(score["beats"][-1]["moving"],[])
        self.assertEqual(score["beats"][-1]["focus"],"fila2")
        self.assertEqual(score["beats"][-1]["visible"],["fila1","fila2"])
        seen=[set(b["moving"]) for b in score["beats"] if b["moving"]]
        self.assertEqual(seen,[{"fila1","fila2"}])
        sample,_,_=brief.direction.frame(v,v["scenes"][1],0)
        later,_,_=brief.direction.frame(v,v["scenes"][1],40)
        self.assertEqual(sample.tobytes(),later.tobytes())

    def test_previous_delivery_survives_failed_rebuild_and_modified_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/"export";out.mkdir()
            movie=out/"video.mp4";movie.write_bytes(b"previous verified output")
            narrated.write(out/"verificacion.json",{"schema":brief.FORM,"files":{"video.mp4":brief.sha(movie)}})
            with patch.object(brief,"make_audio",side_effect=ValueError("test failure")):
                with self.assertRaisesRegex(ValueError,"test failure"):
                    brief.build(EXAMPLES/"recorrido-brief.json",out,"vertical",replace=True)
            self.assertEqual(movie.read_bytes(),b"previous verified output")
            movie.write_bytes(b"user change")
            with self.assertRaisesRegex(ValueError,"modificados"):brief.check_target(out,True)


if __name__=="__main__":
    unittest.main()
