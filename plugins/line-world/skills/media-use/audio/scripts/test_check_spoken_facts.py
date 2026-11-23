import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import wave

import check_spoken_facts as facts


def word(text, start, end):
    return {"word": text, "start": start, "end": end}


def transcript(words, media_sha="a" * 64):
    return {"version": 1, "words": words,
            "origin": {"method": "unprompted-asr", "provider": "test engine", "language": "es",
                       "audioStream": facts.TRACK, "clock": facts.CLOCK, "mediaSha256": media_sha}}


def check(words, expressions, start=0, end=9):
    instruction = {"id": "valor", "start": start, "end": end, "expressions": expressions}
    return facts.check_window(instruction, words, facts.timed_tokens(words))


class SpokenExpressionsTest(unittest.TestCase):
    def test_signs_and_whole_words(self):
        heard = [word("más", .1, .2), word("seis", .2, .4), word("grados.", .4, .6)]
        self.assertEqual(check(heard, ["menos seis grados"])["status"], "revisar")
        self.assertEqual(check(heard[1:], ["menos seis grados"])["status"], "revisar")
        self.assertEqual(check(heard, ["seis grados"], .2)["status"], "revisar")
        heard[0]["word"] = "menos"
        self.assertEqual(check(heard, ["menos 6 grados", "menos seis grados"])["heard"], heard)
        self.assertEqual(check([word("−6", .1, .3)], ["menos 6"])["status"], "coincide")
        self.assertEqual(check([word("quince", .1, .3)], ["cinco"])["status"], "revisar")

    def test_both_units_and_decimal_precision(self):
        words = [word("23", 0, .2), word("puntos", .21, .4), word("básicos.", .45, .8)]
        self.assertEqual(check(words, ["23 puntos básicos"])["status"], "coincide")
        self.assertEqual(check(words, ["23%", "23 por ciento"])["status"], "revisar")
        self.assertEqual(check([word("23%", 0, .3)], ["23 puntos básicos"])["status"], "revisar")
        split = [word("5", 0, .2), word(",15%", .2, .6)]
        self.assertEqual(check(split, ["5,15%"])["heard"], split)
        for wrong in ["15%", "5", "5,1%", "5,15 puntos básicos"]:
            self.assertEqual(check(split, [wrong])["status"], "revisar")
        self.assertEqual(check(split, ["15%"], start=.2)["status"], "revisar")
        self.assertEqual(check([word("4,92%.", .1, .4)], ["4,92%"])["status"], "coincide")

    def test_currency_is_required_and_dollar_sign_needs_an_explicit_alternative(self):
        split = [word("0", 0, .2), word(",99€,", .2, .5)]
        for expression in ["0,99 euros", "0,99€", "€0,99"]:
            self.assertEqual(check(split, [expression])["heard"], split)
        for wrong in ["0,99 dólares", "0,99 £", "0,99 pesos", "0,99$"]:
            self.assertEqual(check(split, [wrong])["status"], "revisar")
        for missing in ["1", "1%", "1£", "1¥", "1$"]:
            self.assertEqual(check([word(missing, 0, .5)], ["1 euro"])["status"], "revisar")
        self.assertEqual(check([word("€1", 0, .5)], ["1 euro"])["status"], "coincide")
        self.assertEqual(check([word("$1", 0, .5)], ["1 dólar"])["status"], "revisar")
        self.assertEqual(check([word("$1", 0, .5)], ["1 dólar", "1$"])["status"], "coincide")
        self.assertEqual(check([word("1", 0, .5)], ["1 dólar", "1$"])["status"], "revisar")

    def test_windows_cut_words_and_gaps(self):
        words = [word("menos", 1.9, 2.1), word("seis", 2.1, 2.3), word("grados", 2.4, 2.7),
                 word("menos", 5, 5.2), word("seis", 7, 7.2)]
        self.assertEqual(check(words, ["menos seis"], 2, 3)["heard"], words[1:3])
        self.assertEqual(check(words, ["menos seis"], 2, 3)["status"], "revisar")
        self.assertEqual(check(words, ["menos seis"], 3, 9)["status"], "revisar")
        self.assertEqual(check(words, ["menos seis"], 1, 3)["status"], "coincide")
        self.assertEqual(check(words, ["menos seis"], 3, 5)["heard"], [])

    def test_word_clock_and_malformed_imports(self):
        good = transcript([word("menos", .1, .2), word("seis", .2, .3)])
        self.assertEqual(facts.validate_transcript(good, "a"*64, 1), good["words"])
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            facts.validate_transcript(good, "b"*64, 1)
        for key, invalid in (("audioStream", "s:0"), ("clock", "subtitle-time"), ("method", "script"),
                             ("provider", ""), ("language", None)):
            case = copy.deepcopy(good)
            case["origin"][key] = invalid
            with self.subTest(key=key), self.assertRaises(ValueError):
                facts.validate_transcript(case, "a"*64, 1)
        for invalid in (None, {}, [word("", .1, .2)], [word("dos palabras", .1, .2)],
                        [word("voz", -.1, .2)], [word("voz", .2, .1)], [word("voz", False, .2)],
                        [word("voz", .1, float("nan"))], [word("voz", 0, 2)],
                        [word("dos", .1, .4), word("tres", .3, .5)]):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                facts.validate_transcript({**good, "words": invalid}, "a"*64, 1)
        self.assertEqual(facts.validate_transcript({**good, "words":[]}, "a"*64, 1), [])

    def test_invalid_checks(self):
        base = {"id":"delta", "start":0, "end":1, "expressions":["diez grados"]}
        for checks in ([], [base, base], [{**base, "start":0.2, "end":0.2}],
                       [{**base, "end":1.1}], [{**base, "expressions":["!"]}]):
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                facts.validate_checks({"version":1, "checks":checks}, 1)

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg required to decode WAV")
    def test_import_is_bound_to_actual_file_and_outputs_are_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            media, plan, words, report = [Path(folder)/name for name in ("clip.wav", "plan.json", "words.json", "out.json")]
            with wave.open(str(media), "wb") as wav:
                wav.setparams((1, 2, 16000, 0, "NONE", ""))
                wav.writeframes(bytes(32000))
            facts.save(plan, {"version":1, "checks":[{"id":"sign", "start":0, "end":1, "expressions":["menos seis"]}]})
            data = transcript([word("seis", .2, .3)], facts.digest(media))
            facts.save(words, data)
            self.assertEqual(facts.audit(media, plan, words, None, "es", report, None), "revisar")
            self.assertEqual(facts.load(report)["checks"][0]["heard"], data["words"])
            with self.assertRaisesRegex(ValueError, "distinct"):
                facts.audit(media, plan, words, None, "es", media, None)
            # Still a decodable WAV, but a different file.
            with media.open("ab") as handle:
                handle.write(b"changed")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                facts.audit(media, plan, words, None, "es", report, None)

    @unittest.skipUnless(os.getenv("LINE_WORLD_AUDIO_REVIEW_CASES") and shutil.which("ffmpeg"),
                         "Set LINE_WORLD_AUDIO_REVIEW_CASES to the private critique examples")
    def test_actual_freezer_aacs_and_bond_master(self):
        root = Path(os.environ["LINE_WORLD_AUDIO_REVIEW_CASES"])
        freezer = root / "prueba-desde-brief"
        self.assertEqual(facts.digest(freezer/"entrega/brief.json"), facts.digest(freezer/"revisada/brief.json"))
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp)/"control.json"
            for version, decision in (("entrega","revisar"), ("revisada","coincide")):
                self.assertEqual(facts.audit(freezer/version/"video.mp4", freezer/"hechos-hablados.json",
                                             freezer/f"palabras-{version}.json", None, "es", report, None), decision)
                results = {r["id"]:r["status"] for r in facts.load(report)["checks"]}
                self.assertEqual(results, {"inicio-positivo":"coincide", "final-negativo":decision, "diferencia":"coincide"})
            bonds = root/"voces"
            self.assertEqual(facts.audit(bonds/"mezcla/master.wav", bonds/"hechos-hablados.json",
                                         bonds/"palabras-control.json", None, "es", report, None), "coincide")
            self.assertEqual(len(facts.load(report)["checks"]), 3)


if __name__ == "__main__":
    unittest.main()
