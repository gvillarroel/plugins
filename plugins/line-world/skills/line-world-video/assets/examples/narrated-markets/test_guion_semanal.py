"""Comprueba el borrador de otra semana sin Internet ni modelos de voz."""
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from generar import normalize,plan
from preparar_guion import draft,integer,level,movement,period,rate_text,words


HERE=Path(__file__).resolve().parent


def historical():
    pairs={"sp500":("S&P 500","puntos",7561.67,6910.39),"nasdaq":("Nasdaq Composite","puntos",25136.27,22617.73),
           "oro":("Oro al contado","USD por onza troy",3880.70,3532.85),"btc":("Bitcoin","USD por BTC",68249.27,58798.98),
           "tlt":("Bonos del Tesoro","USD por participación",79.38,81.45),"ust10":("Tesoro a 10 años","rendimiento anual, %",5.15,4.92)}
    dates=["2026-11-13","2026-11-20"]
    urls={"sp500":"https://fred.stlouisfed.org/series/SP500",
          "nasdaq":"https://api.nasdaq.com/api/quote/COMP/historical?assetclass=index&fromdate=2026-11-13&todate=2026-11-20",
          "oro":"https://www.investing.com/currencies/xau-usd-historical-data",
          "btc":"https://coinmarketcap.com/historical/20261120/",
          "tlt":"https://api.nasdaq.com/api/quote/TLT/historical?assetclass=etf&fromdate=2026-11-13&todate=2026-11-20",
          "ust10":"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve&field_tdr_date_value_month=202611"}
    return {"inicio":dates[0],"fin":dates[-1],"semana":"16–20 noviembre 2026","mercado":"EE. UU.",
            "series":{key:{"nombre":name,"unidad":unit,"tipo":"rendimiento" if key=="ust10" else "precio",
                          "values":[first,last],"fechas":dates,"fuentes":[urls[key]]}
                      for key,(name,unit,first,last) in pairs.items()}}


def texts(audio):return {s["id"]:s["text"] for s in audio["scenes"]}


def measured(audio):
    rate=48000;cursor=0;scenes=[]
    for scene in audio["scenes"]:
        phrases=re.split(r"(?<=[.!?])\s+",scene["text"])
        start=cursor
        sentences=[]
        for phrase in phrases:
            sentences.append({"text":phrase,"absolute_start_sample":cursor+1000,"absolute_end_sample":cursor+rate-1000})
            cursor+=rate
        scenes.append({"id":scene["id"],"start_sample":start,"end_sample":cursor,"sentences":sentences})
    return {"sample_rate":rate,"master":{"samples":cursor},"scenes":scenes}


class WeeklyDraft(unittest.TestCase):
    def test_historical_signs_levels_rank_and_basis_points(self):
        data=historical();audio,visual=draft(data)
        self.assertEqual(audio["caption_layout"],"es-lectura")
        s=texts(audio)
        self.assertTrue(s["intro"].startswith("Del dieciséis al veinte de noviembre"))
        self.assertEqual(list(s),["intro","bolsa","oro","btc","bonos"])
        for key,fragment in [("intro","cuatro de las cinco referencias de precio bajaron"),("bolsa","diez coma cero dos"),
                             ("oro","ocho coma noventa y seis por ciento"),("oro","tres mil quinientos treinta y dos coma ochenta y cinco dólares por onza troy"),
                             ("oro","tercera mayor caída"),("btc","cincuenta y ocho mil setecientos noventa y ocho coma noventa y ocho dólares por bitcóin"),
                             ("btc","registró la mayor caída"),
                             ("bonos","subió un dos coma sesenta y uno por ciento"),("bonos","cinco coma quince a cuatro coma noventa y dos"),
                             ("bonos","bajada de veintitrés puntos básicos")]:
            self.assertIn(fragment,s[key])
        for orientation in (True,False):
            shots,score=plan(measured(audio),visual,orientation,normalize(data))
            self.assertEqual(len(shots),11)
            self.assertTrue(score["beats"])

    def test_tie_flat_price_rising_yield_and_custom_synthetic_names(self):
        data=historical();data.update(sintetico=True,procedencia="Ejercicio",orden=["btc","oro","tlt","nasdaq","sp500"])
        for key,n in zip(("sp500","nasdaq","oro","btc","tlt"),(105,105,94,94,100)):data["series"][key]["values"]=[100,n]
        data["series"]["oro"]["nombre_hablado"]="El metal de EE. UU."
        data["series"]["ust10"]["values"]=[-.50,-.29]
        audio,visual=draft(data);s=texts(audio)
        self.assertIn("datos de prueba",s["intro"])
        self.assertIn("empate con dos bajas y dos alzas",s["intro"])
        self.assertIn("El metal de Estados Unidos bajó",s["oro"])
        self.assertIn("Compartió la mayor caída",s["oro"])
        self.assertIn("menos cero coma cinco a menos cero coma veintinueve",s["bonos"])
        self.assertIn("subida de veintiún puntos básicos",s["bonos"])
        plan(measured(audio),visual,True,normalize(data))
        for series in data["series"].values():series["values"][-1]=series["values"][0]
        audio,visual=draft(data);s=texts(audio)
        self.assertIn("las cinco referencias de precio cerraron sin cambio",s["intro"])
        self.assertIn("se mantuvo en menos cero coma cinco por ciento",s["bonos"])
        self.assertNotIn("mayor caída",s["oro"])
        plan(measured(audio),visual,False,normalize(data))
        for key,series in data["series"].items():
            if key!="ust10":series["values"][-1]=106
        audio,_=draft(data)
        self.assertIn("las cinco referencias de precio subieron",texts(audio)["intro"])
        self.assertIn("Compartió la mayor alza",texts(audio)["oro"])

    def test_dates_tiny_moves_singular_units_and_numbers(self):
        self.assertEqual(integer(21000001),"veintiún millones uno")
        self.assertEqual(words("0.01"),"cero coma cero uno")
        self.assertEqual(period("2026-12-30","2027-01-04"),"del treinta de diciembre de dos mil veintiséis al cuatro de enero de dos mil veintisiete")
        self.assertIn("menos de un cero coma cero uno por ciento",movement("X",Fraction(1,1000)))
        self.assertIn("subió cero coma veinticinco puntos básicos",rate_text(dict(nombre="Tasa",values=[4.0,4.0025])))
        self.assertEqual(level(dict(values=[3,1],unidad="USD por unidad")),"un dólar por unidad")
        self.assertEqual(level(dict(values=[2,10**6],unidad="USD por unidad")),"un millón de dólares por unidad")

    def test_destination_preserves_edits_and_preview_needs_no_output(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base);data=root/"datos.json";data.write_text(json.dumps(historical()),encoding="utf-8")
            command=[sys.executable,"-B",str(HERE/"preparar_guion.py"),"--datos",str(data)]
            run=lambda *args:subprocess.run([*command,*args],cwd=root,capture_output=True)
            self.assertEqual(run("--preview").returncode,0)
            self.assertEqual(len(list(root.iterdir())),1)
            self.assertEqual(run("--out","guion").returncode,0)
            edited=root/"guion/narracion.json";edited.write_text("revisión local",encoding="utf-8")
            self.assertNotEqual(run("--out","guion").returncode,0)
            self.assertEqual(edited.read_text(encoding="utf-8"),"revisión local")


if __name__=="__main__":unittest.main()
