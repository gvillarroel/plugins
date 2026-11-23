import contextlib
import io
import json
from datetime import date
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import cierres


SESSIONS=("2026-01-30","2026-02-02")
DAILY=("2026-01-30","2026-01-31","2026-02-01","2026-02-02")


def evidence():
    providers={}
    def row(key,d,value,raw):
        p=providers.setdefault(key,{"url":"https://provider.example/"+key,"status":"rows","rows":{}})
        p["rows"][d]={"value":value,"originalRow":raw}
    for i,d in enumerate(SESSIONS):
        t=date.fromisoformat(d);price=str(101+i)
        row("fred",d,price,{"observation_date":d,"SP500":price})
        row("cboe",d,price,{"DATE":t.strftime("%m/%d/%Y"),"SPX":price})
        for key in ("comp","tlt"):
            row(key,d,price,{"date":t.strftime("%m/%d/%Y"),"close":price})
        row("xau",d,price,{"Date":t.strftime("%b %d, %Y"),"Price":price})
        key="tesoro" if i==0 else "tesoro/202602"
        row(key,d,"4.35",{"NEW_DATE":d+"T00:00:00","BC_10YEAR":"4.35"})
    for i,d in enumerate(DAILY):
        price=str(100+i)+".358"
        row("btc-ohlc",d,price,{"timeOpen":d+"T00:00:00.000Z","timeClose":d+"T23:59:59.999Z",
                               "quote":{"name":"2781","timestamp":d+"T23:59:59.999Z","close":price}})
    return {"version":1,"start":SESSIONS[0],"end":SESSIONS[-1],"providers":providers}


class ProviderReceipts(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.rec=self.root/"receipt.json";self.out=self.root/"episode.json"
        self.data=evidence();self.write_receipt()

    def write_receipt(self):
        self.rec.write_text(json.dumps(self.data),encoding="utf-8")

    def export(self):
        with contextlib.redirect_stdout(io.StringIO()):
            cierres.extract_episode(self.rec,self.out)
        return json.loads(self.out.read_text(encoding="utf-8"))

    def test_two_months_six_series_separate_price_and_utc_clock(self):
        result=self.export()
        self.assertEqual(result["semana"],"30 enero–2 febrero 2026")
        self.assertEqual(result["series"]["btc"]["values"],[100.36,101.36,102.36,103.36])
        self.assertEqual(result["series"]["ust10"]["fechas"],list(SESSIONS))
        self.assertEqual(result["series"]["tlt"]["unidad"],"USD por participación de TLT")
        links=cierres.source_urls(*map(date.fromisoformat,SESSIONS))
        self.assertIn("202601",links["tesoro"]);self.assertIn("202602",links["tesoro/202602"])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cierres.compare(self.out,self.rec,self.root/"verified"),0)

    def test_headline_and_price_baseline_have_different_clocks(self):
        for first, last, monday in (
            ("2026-11-13","2026-11-20","2026-11-16"),
            ("2026-06-26","2026-07-03","2026-06-29"),
            ("2026-12-25","2027-01-01","2026-12-28"),
            ("2026-01-30","2026-02-02","2026-01-30"),
        ):
            with self.subTest(first=first,last=last):
                start,end=map(date.fromisoformat,(first,last))
                self.assertEqual(cierres.validar.headline_start(start,end).isoformat(),monday)

    def test_amount_and_nav_and_calendar_field_cannot_replace_an_original_close(self):
        d=SESSIONS[0]
        for edit,error in [
            (lambda s:s["tlt"]["rows"][d].update(originalRow={"As Of":d,"NAV per Share":"101"}),"cierre de mercado"),
            (lambda s:s["comp"]["rows"][d].update(value="999"),"fila original"),
            (lambda s:s["btc-ohlc"]["rows"][d]["originalRow"].update(timeClose=d+"T12:00:00.000Z"),"UTC"),
            (lambda s:s["btc-ohlc"]["rows"][d]["originalRow"]["quote"].update(name="978"),"moneda"),
            (lambda s:s["fred"]["rows"][d]["originalRow"].update(observation_date=SESSIONS[1]),"fecha original"),
        ]:
            with self.subTest(error=error):
                self.data=evidence();edit(self.data["providers"]);self.write_receipt()
                with self.assertRaisesRegex(ValueError,error):self.export()
                self.assertFalse(self.out.exists())

    def test_missing_day_or_provider_does_not_create_an_episode(self):
        for source,d,error in (("btc-ohlc",DAILY[2],"faltan cierres UTC"),("xau",SESSIONS[0],"faltan observaciones")):
            with self.subTest(source=source):
                self.data=evidence();self.data["providers"][source]["rows"].pop(d);self.write_receipt()
                with self.assertRaisesRegex(ValueError,error):self.export()
                self.assertFalse(self.out.exists())
        self.data=evidence()
        self.data["providers"]["tlt"]["observedDates"]=list(SESSIONS)
        self.data["providers"]["tlt"]["rows"].pop(SESSIONS[1])
        self.write_receipt()
        with self.assertRaisesRegex(ValueError,"captura"):self.export()

    def test_failed_capture_preserves_a_dated_receipt_and_aborts_export(self):
        snapshot=self.root/"partial.json"
        with patch.object(cierres,"fetch",side_effect=OSError("Public endpoint temporarily unavailable")), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cierres.collect(*map(date.fromisoformat,SESSIONS),snapshot),1)
        frozen=json.loads(snapshot.read_text(encoding="utf-8"))
        self.assertEqual(frozen["providers"]["xau"]["status"],"unavailable")
        self.assertIn("Public endpoint",frozen["providers"]["xau"]["error"])
        self.assertEqual(frozen["series"]["tlt"]["unit"],cierres.UNIT["tlt"])
        with self.assertRaisesRegex(ValueError,"faltan observaciones"):
            cierres.extract_episode(snapshot,self.out)
        self.assertFalse(self.out.exists())

    def test_crosscheck_and_sessions_are_independent_of_the_episode(self):
        self.data["providers"]["cboe"]["rows"][SESSIONS[1]].update(value="999",originalRow={"DATE":"02/02/2026","SPX":"999"})
        self.write_receipt()
        with self.assertRaisesRegex(ValueError,"discrepan"):self.export()
        self.data=evidence();self.write_receipt()
        sessions=self.root/"calendar.json";sessions.write_text(json.dumps({"ust10":list(DAILY)}))
        with self.assertRaisesRegex(ValueError,"calendario"):cierres.extract_episode(self.rec,self.out,sessions)

    def test_source_observations_preserve_prior_files_and_directories(self):
        self.export();before=self.out.read_bytes()
        with self.assertRaises(FileExistsError):self.export()
        self.assertEqual(self.out.read_bytes(),before)
        outdir=self.root/"previous";outdir.mkdir();(outdir/"cierres.csv").write_text("previo")
        with self.assertRaises(FileExistsError):cierres.compare(self.out,self.rec,outdir)
        self.assertEqual((outdir/"cierres.csv").read_text(),"previo")
        with self.assertRaises(FileExistsError):cierres.write_new(self.rec,{"new":True})
        self.assertEqual(json.loads(self.rec.read_bytes()),self.data)

    def test_wrong_currency_in_the_episode_fails_before_creating_comparison(self):
        data=self.export();data["series"]["oro"]["unidad"]="EUR por onza troy"
        self.out.write_text(json.dumps(data))
        dest=self.root/"no-publicar"
        with self.assertRaisesRegex(ValueError,"unidad"):cierres.compare(self.out,self.rec,dest)
        self.assertFalse(dest.exists())

    def test_cli_runs_outside_the_checkout(self):
        r=subprocess.run([sys.executable,"-B",cierres.__file__,"export",str(self.rec),str(self.out)],
                         cwd=self.root,capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertTrue(self.out.is_file())


if __name__=="__main__":
    unittest.main()
