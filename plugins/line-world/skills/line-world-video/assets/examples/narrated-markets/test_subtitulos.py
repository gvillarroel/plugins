"""Regression tests for verbatim Spanish captions and audio-clock provenance."""
import json
from pathlib import Path
import tempfile
import unittest

from generar import audio_clock
from spanish_captions import compose, divide, quantities


def phrase(text):
    return {"text":text,"absolute_start_sample":1000,"absolute_end_sample":9000}


class Subtitles(unittest.TestCase):
    def test_numbers_and_units_survive_every_break(self):
        text="Esa semana, el rendimiento del Tesoro a diez años bajó del cinco coma quince al cuatro coma noventa y dos por ciento."
        cues=divide(phrase(text),1000,[])
        lines=[line for cue in cues for line in cue["text"].splitlines()]
        self.assertEqual(" ".join(lines), text)
        for measure in ("diez años","cinco coma quince","cuatro coma noventa y dos por ciento"):
            self.assertTrue(any(measure in line for line in lines),measure)
        self.assertTrue(all(len(line)<=42 for line in lines))
        self.assertTrue(all(len(c["text"].splitlines())<=2 for c in cues))

    def test_long_quantity_keeps_its_event_and_second_numeral(self):
        text="Pasó de unos tres mil ochocientos ochenta dólares por onza a tres mil quinientos treinta y tres."
        cues=divide(phrase(text),1000,[])
        normalized=[" ".join(c["text"].split()) for c in cues]
        for measure in ("tres mil ochocientos ochenta dólares por onza","tres mil quinientos treinta y tres."):
            self.assertTrue(any(measure in cue for cue in normalized),measure)
        self.assertEqual(quantities("5,15 % y veinte años".split()),[(0,2),(3,5)])

    def test_edited_breaks_use_proven_word_or_explicit_estimate(self):
        p=phrase("Hoy baja el precio y mañana sube el rendimiento.")
        layout=["Hoy baja el precio","y mañana sube el rendimiento."]
        marks=[{"word":"y","start":4,"end":4.1},{"word":"mañana","start":4.1,"end":4.7}]
        one,two=divide(p,1000,marks,layout)
        self.assertEqual((one["endMs"],two["startMs"],two["startBasis"]),(4000,4000,"asr"))
        self.assertEqual(divide(p,1000,[],layout)[1]["startBasis"],"estimated")
        with self.assertRaisesRegex(ValueError,"recorded words"):
            divide(p,1000,marks,["Hoy bajó el precio","y mañana sube el rendimiento."])

    def test_rejects_partial_cents_and_rate_lines(self):
        p=phrase("Bajó del cinco coma quince al cuatro coma noventa y dos por ciento.")
        with self.assertRaisesRegex(ValueError,"separates"):
            divide(p,1000,[],["Bajó del cinco","coma quince al cuatro coma noventa y dos\npor ciento."])
        with self.assertRaisesRegex(ValueError,"separates"):
            divide(phrase("Una caída de casi el nueve por ciento."),1000,[],["Una caída de casi el nueve por\nciento."])

    def test_clock_identity_and_monotonicity(self):
        clock={"master":{"sha256":"abc"},"sample_rate":1000,"scenes":[{"id":"a","sentences":[phrase("Hoy.")]}]}
        data={"origin":{"mediaSha256":"other","clock":"seconds-from-first-decoded-sample"},"words":[]}
        with self.assertRaisesRegex(ValueError,"exact audio"):
            compose(clock,data)
        data["origin"]["mediaSha256"]="abc"
        data["words"]=[{"word":"Hoy","start":4,"end":3}]
        with self.assertRaisesRegex(ValueError,"ordered"):
            compose(clock,data)
        data.update(words=[],subtitleLayouts={"bad/1":["Hoy."]})
        with self.assertRaisesRegex(ValueError,"unknown"):
            compose(clock,data)

    def test_long_price_keeps_decimal_and_denomination_in_one_event(self):
        value="sesenta y ocho mil doscientos cuarenta y nueve coma veintisiete dólares por bitcóin."
        text="El cierre del viernes, medido al final del día en horario UTC, fue de "+value
        cues=divide(phrase(text),1000,[])
        price=next(c for c in cues if "veintisiete" in c["text"])
        self.assertEqual(" ".join(price["text"].split()),value)
        self.assertEqual(price.get("longQuantityLine"),43)
        self.assertEqual(price["text"].splitlines()[1],"nueve coma veintisiete dólares por bitcóin.")
        self.assertTrue(all(len(line)<=42 for c in cues if c is not price for line in c["text"].splitlines()))

    def test_supplied_timeline_and_captions_are_preserved_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            wav=base/"timeline.json"
            wav.write_text(json.dumps({"sample_rate":1000}),encoding="utf-8")
            provided=b"1\r\n00:00:00,100 --> 00:00:01,400\r\nUn texto propio.\r\n"
            (base/"captions.srt").write_bytes(provided)
            self.assertEqual(audio_clock(base,base/"nuevo",{"words":[]}),wav)
            self.assertEqual((base/"captions.srt").read_bytes(),provided)
            self.assertFalse((base/"nuevo").exists())


if __name__=="__main__":
    unittest.main()
