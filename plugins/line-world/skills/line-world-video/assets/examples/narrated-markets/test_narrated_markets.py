#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.51,<2"]
# ///
"""Check synthetic holiday, breadth and bond cases at the actual canvas sizes."""
import copy
import json
import os
import unittest
from pathlib import Path

from playwright.sync_api import Error as BrowserError, sync_playwright

from generar import FPS, normalize, plan


HERE = Path(__file__).resolve().parent
FIRST, LAST = "2026-11-20", "2026-11-27"
HOLIDAY = "2026-11-26"


def fixture():
    return {
        "inicio": FIRST, "fin": LAST, "semana": "20–27 noviembre", "mercado": "EE. UU.",
        "sintetico": True, "procedencia": "escenario ficticio de festivo y cierres",
        "series": {
            "sp500": {"nombre": "S&P 500", "tipo": "precio", "unidad": "Puntos",
                      "fechas": [FIRST, "2026-11-23", "2026-11-25", LAST], "values": [100, 99, 99, 98]},
            "nasdaq": {"nombre": "Nasdaq", "tipo": "precio", "unidad": "Puntos",
                       "fechas": ["2026-11-23", "2026-11-25"], "values": [100, 104]},
            "oro": {"nombre": "Oro", "tipo": "precio", "unidad": "USD por onza",
                    "fechas": [FIRST, LAST], "values": [100, 97]},
            "btc": {"nombre": "Bitcoin", "tipo": "precio", "unidad": "USD",
                    "fechas": [f"2026-11-{day}" for day in range(20, 28)], "values": [100, 102, 103, 99, 102, 104, 103, 106]},
            "tlt": {"nombre": "Bonos del Tesoro", "tipo": "precio", "unidad": "USD",
                    "fechas": [FIRST, "2026-11-25", LAST], "values": [100, 102, 100]},
            "ust10": {"nombre": "Tesoro a 10 años", "tipo": "rendimiento", "unidad": "rendimiento anual, %",
                      "fechas": [FIRST, "2026-11-25", LAST], "values": [0, .01, 0]},
        },
    }


NARRATION = [
    "Dos referencias subieron y dos bajaron.",
    "¿Y el precio de un bono?",
    "Con la misma tasa no cambia el descuento.",
    "El fondo cerró sin cambio.",
    "Comparamos dos cierres observados del oro.",
    "Bitcoin tiene observaciones del fin de semana.",
    "La tasa anual acabó en cero.",
]


def recipe():
    return [
        {"scene": "fixture", "sentence": index, "view": view, "series": key, "metric": metric,
         "from": 0, "to": 1, "idea": NARRATION[index]}
        for index, (view, key, metric) in enumerate([
            ("breadth", "conjunto", "breadth"), ("coupon", "ust10", "question"), ("coupon", "ust10", "mechanism"),
            ("ranking", "tlt", "change"), ("line", "oro", "change"), ("line", "btc", "level"),
            ("line", "ust10", "yield"),
        ])
    ]


def timeline():
    rate=48000
    length=len(NARRATION)*2*rate
    return {"sample_rate": rate, "master": {"samples": length},
            "scenes": [{"id": "fixture", "start_sample": 0, "end_sample": length, "sentences": [
                {"text": line, "absolute_start_sample": index*2*rate, "absolute_end_sample": (index*2+1)*rate}
                for index,line in enumerate(NARRATION)
            ]}]}


def html(data, shots, viewport):
    payload=json.dumps({"data":data, "shots":shots, "fps":FPS}, ensure_ascii=False).replace("<", "\\u003c")
    width,height=viewport
    return (HERE/"escena.html").read_text(encoding="utf-8").replace("__PAYLOAD__",payload).replace("__WIDTH__",str(width)).replace("__HEIGHT__",str(height))


class MarketInputs(unittest.TestCase):
    def test_measured_word_cut_follows_two_recordings_and_rejects_stale_alignment(self):
        visual=recipe()
        visual[5]["startOn"]="y cerró"
        measured=timeline()
        measured["master"]["sha256"]="1"*64
        measured["scenes"][0]["sentences"][5]["text"]="El precio cayó y cerró más bajo."
        evidence={"origin":{"mediaSha256":"1"*64,"clock":"seconds-from-first-decoded-sample"},"words":[]}
        for onset,expected in [(10.14,305),(10.54,317)]:
            evidence["words"]=[{"word":"y","start":onset,"end":onset+.05},
                               {"word":"cerró","start":onset+.05,"end":onset+.17}]
            shots,_=plan(measured,visual,False,normalize(fixture()),evidence)
            self.assertEqual((shots[4]["end"],shots[5]["start"]),(expected,expected))
        evidence["origin"]["mediaSha256"]="2"*64
        with self.assertRaisesRegex(ValueError,"master WAV"):
            plan(measured,visual,False,normalize(fixture()),evidence)
        evidence["origin"]["mediaSha256"]="1"*64
        evidence["words"]=[{"word":"y","start":9.65,"end":9.7},{"word":"cerró","start":9.71,"end":9.8}]
        with self.assertRaisesRegex(ValueError,"one measured occurrence"):
            plan(measured,visual,False,normalize(fixture()),evidence)

    def test_holiday_and_stock_crypto_calendars_keep_observed_dates(self):
        data=normalize(fixture())
        stock=data["series"]["sp500"]
        btc=data["series"]["btc"]
        self.assertNotIn(HOLIDAY,stock["fechas"])
        self.assertIn(HOLIDAY,btc["fechas"])
        self.assertIn("2026-11-21",btc["fechas"])
        self.assertEqual(data["series"]["nasdaq"]["fechas"], ["2026-11-23","2026-11-25"])
        legacy=fixture()
        series=legacy["series"]["oro"]
        series["dias"]=[20,27]
        del series["fechas"]
        self.assertEqual(normalize(legacy)["series"]["oro"]["fechas"], [FIRST,LAST])

    def test_zero_prices_and_null_observations_report_the_series_and_date(self):
        for key,value,error in [("tlt",0,"price"),("tlt",None,"observation"),("ust10",None,"observation")]:
            with self.subTest(key=key,value=value):
                data=fixture()
                data["series"][key]["values"][0]=value
                with self.assertRaisesRegex(ValueError, rf"{key} \({FIRST}\): .*{error}"):
                    normalize(data)
        self.assertEqual(normalize(fixture())["series"]["ust10"]["values"][0], 0)

    def test_invalid_dates_are_named(self):
        for value,error in [("2026-11-29","outside"),("2026-11-00","session date"),(FIRST,"chronological")]:
            with self.subTest(value=value):
                data=fixture()
                data["series"]["oro"]["fechas"][-1]=value
                with self.assertRaisesRegex(ValueError,rf"oro: .*{error}"):
                    normalize(data)

    def test_flat_coupon_and_flat_price_have_reading_only_beats(self):
        shots,score=plan(timeline(),recipe(),True,normalize(fixture()))
        for index in (1,2,3):
            shot=shots[index]
            beats=[b for b in score["beats"] if shot["start"]<=b["start"]<shot["end"]]
            self.assertEqual([(b["mode"], b["moving"]) for b in beats], [("read",[])])
            self.assertEqual(shot["stop"], shot["start"])

    def test_spoken_approximation_requires_matching_phrase_and_observations(self):
        data=fixture()
        data["series"]["oro"]["values"]=[100,91.04]
        visual=recipe()
        visual[3].update(series="oro", metric="rank", approxPercent=9, spokenApprox="casi el nueve por ciento")
        measured=timeline()
        with self.assertRaisesRegex(ValueError,"exact corresponding quote"):
            plan(measured,visual,True,normalize(data))
        measured["scenes"][0]["sentences"][3]["text"]="El oro cayó casi el nueve por ciento."
        shots,_=plan(measured,visual,True,normalize(data))
        self.assertEqual(shots[3]["approxPercent"],9)
        for close in (91,90.9,92):
            data["series"]["oro"]["values"][-1]=close
            with self.assertRaisesRegex(ValueError,"below the spoken approximation"):
                plan(measured,visual,True,normalize(data))


class MarketFrames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime=sync_playwright().start()
        cls.addClassCleanup(cls.runtime.stop)
        try:
            cls.browser=cls.runtime.chromium.launch()
        except BrowserError as error:
            if os.name!="nt" or "Executable doesn't exist" not in str(error):
                raise
            cls.browser=cls.runtime.chromium.launch(channel="msedge")
        cls.addClassCleanup(cls.browser.close)

    def load(self,data,viewport,visual=None,recorded=None):
        data=normalize(copy.deepcopy(data))
        shots,_=plan(recorded or timeline(),visual or recipe(),viewport[0]==390,data)
        page=self.browser.new_page(viewport={"width":viewport[0],"height":viewport[1]})
        self.addCleanup(page.close)
        page.set_content(html(data,shots,viewport))
        page.evaluate(r"""()=>{
          const ctx=document.querySelector("canvas").getContext("2d");
          const old={};
          for(const name of ["fillText","beginPath","moveTo","lineTo","stroke","arc"])old[name]=ctx[name].bind(ctx);
          let path=[];
          ctx.beginPath=()=>{path=[];old.beginPath()};
          ctx.moveTo=(x,y)=>{path.push([x,y]);old.moveTo(x,y)};
          ctx.lineTo=(x,y)=>{path.push([x,y]);old.lineTo(x,y)};
          ctx.arc=(x,y,...rest)=>{arcs.push({x,y});old.arc(x,y,...rest)};
          ctx.stroke=()=>{strokes.push({color:ctx.strokeStyle,path});old.stroke()};
          ctx.fillText=(s,x,y,...rest)=>{
            const m=ctx.measureText(s);
            drawn.push({s, x, y, color:ctx.fillStyle, font:parseFloat(ctx.font.match(/(\d+(?:\.\d+)?)px/)[1]),
              box:[x-m.actualBoundingBoxLeft,y-m.actualBoundingBoxAscent,x+m.actualBoundingBoxRight,y+m.actualBoundingBoxDescent]});
            old.fillText(s,x,y,...rest);
          };
          window.inspectFrame=frame=>{
            window.drawn=[];window.strokes=[];window.arcs=[];
            const state=renderAt(0,frame);
            return {state,drawn,strokes,arcs};
          };
        }""")
        return page,shots

    def frame(self,page,number,viewport):
        pose=page.evaluate("frame=>inspectFrame(frame)", number)
        rows=pose["drawn"]
        self.assertTrue(any("DATOS SINTÉTICOS" in row["s"] for row in rows))
        w,h=viewport
        for row in rows:
            x1,y1,x2,y2=row["box"]
            self.assertTrue(-.5<=x1<=x2<=w+.5 and -.5<=y1<=y2<=h+.5,row)
            # Two default WebVTT lines occupy the bottom 88 px or 48 px at these sizes.
            self.assertLessEqual(y2,h-(48 if w==390 else 88),row)
            if w==390:
                self.assertGreaterEqual(row["font"],13)
        for index,a in enumerate(rows):
            x1,y1,x2,y2=a["box"]
            for b in rows[index+1:]:
                u1,v1,u2,v2=b["box"]
                self.assertFalse(min(x2,u2)-max(x1,u1)>1 and min(y2,v2)-max(y1,v1)>1,(a,b))
        return pose

    def test_flat_tie_sparse_and_weekend_frames_at_both_sizes(self):
        for viewport in ((1280,720),(390,844)):
            with self.subTest(viewport=viewport):
                page,shots=self.load(fixture(),viewport)
                poses=[self.frame(page,s["end"]-1,viewport) for s in shots]
                texts=[[r["s"] for r in pose["drawn"]] for pose in poses]
                self.assertIn("Empate",texts[0])
                self.assertIn("Bajas y Alzas · 2 de 5 por grupo",texts[0])
                self.assertFalse(any("Filas señaladas" in s or "4/4" in s for s in texts[0]))
                self.assertIn("Empate",[r["s"] for r in self.frame(page,0,viewport)["drawn"]])
                self.assertIn("Cierres según mercado"," ".join(texts[0]))
                self.assertIn("TLT · bonos >20 años",texts[0])
                self.assertIn("TLT: USD por participación"," ".join(texts[0]))
                self.assertIn("¿Y su precio?",texts[1])
                self.assertIn("El descuento se mantiene.",texts[2])
                self.assertIn("El valor presente no cambia por la tasa.",texts[2])
                self.assertIn("0,00 %",texts[3])
                for index in (1,2,3):
                    images=page.evaluate("fs=>fs.map(f=>{renderAt(0,f);return document.querySelector('canvas').toDataURL()})",
                                         [shots[index]["start"],shots[index]["end"]-1])
                    self.assertEqual(images[0],images[1])
                tick_y=590 if viewport[0]==1280 else 698
                self.assertEqual([r["s"] for r in poses[4]["drawn"] if r["y"]==tick_y], ["20 nov","27 nov"])
                self.assertEqual([r["s"] for r in poses[5]["drawn"] if r["y"]==tick_y], ["20 nov","23 nov","27 nov"])
                self.assertIn("Cierre del 27 nov · USD",texts[5])
                self.assertIn("0 pb",texts[6])

    def test_opening_count_is_fixed_and_gold_ranking_keeps_percent_in_row(self):
        fixture_data=fixture()
        fixture_data["series"]["btc"]["values"][-1]=90
        visual=recipe()
        visual[3].update(series="oro",metric="rank")
        for viewport in ((1280,720),(390,844)):
            with self.subTest(viewport=viewport):
                page,shots=self.load(fixture_data,viewport,visual)
                opening=shots[0]
                rows=page.evaluate("([a,b])=>Array.from({length:b-a},(_,i)=>inspectFrame(a+i))",
                                   [opening["start"],opening["stop"]])
                counts=[]
                marker_x=552 if viewport[0]==1280 else 11
                for frame in rows:
                    texts=[r["s"] for r in frame["drawn"]]
                    self.assertIn("3 de 5",texts)
                    self.assertIn("referencias bajaron",texts)
                    self.assertFalse(any("Filas señaladas" in s or "/" in s and s[0].isdigit() for s in texts))
                    marked=[s for s in frame["strokes"] if s["color"]=="#9e1b32" and s["path"][0][0]==marker_x]
                    support_x=1157 if viewport[0]==1280 else 327
                    support=[s for s in frame["strokes"] if s["color"]=="#696969" and s["path"][0][0]==support_x]
                    self.assertEqual(len(marked),len(support))
                    counts.append(len(marked))
                self.assertEqual(sorted(set(counts)),[0,1,2,3])
                self.assertEqual(counts,sorted(counts))
                shot=shots[3]
                rank=self.frame(page,shot["end"]-1,viewport)
                texts=[r["s"] for r in rank["drawn"]]
                self.assertIn("2.ª mayor caída",texts)
                self.assertEqual(texts.count("−3,00 %"),1)
                self.assertEqual([r["color"] for r in rank["drawn"] if r["s"]=="−3,00 %"],["#9e1b32"])
                selected_y=next(r["y"] for r in rank["drawn"] if r["s"]=="−3,00 %")
                top,bottom=(-21,1) if viewport[0]==1280 else (-4,12)
                row_marks=[s["path"] for s in rank["strokes"] if len(s["path"])==2 and all(p[0]==marker_x for p in s["path"])]
                self.assertEqual(row_marks,[[[marker_x,selected_y+top],[marker_x,selected_y+bottom]]])
                self.assertEqual(rank["state"]["mode"],"read")

    def test_all_flat_and_all_rising_open_with_the_complete_count(self):
        for viewport in ((1280,720),(390,844)):
            for close,verb in ((100,"quedaron sin cambio"),(105,"subieron")):
                data=fixture()
                for key in ("sp500","nasdaq","oro","btc","tlt"):
                    data["series"][key]["values"][-1]=close
                page,_=self.load(data,viewport)
                texts=[r["s"] for r in self.frame(page,0,viewport)["drawn"]]
                self.assertIn("5 de 5",texts)
                self.assertIn("referencias "+verb,texts)
                self.assertFalse(any("Filas señaladas" in s for s in texts))

    def test_narrated_rounding_is_primary_and_keeps_exact_price_in_one_row(self):
        data=fixture()
        data["series"]["oro"]["values"][-1]=91.04
        visual=recipe()
        visual[3].update(series="oro",metric="rank",approxPercent=9,spokenApprox="casi el nueve por ciento")
        measured=timeline()
        measured["scenes"][0]["sentences"][3]["text"]="El oro cayó casi el nueve por ciento."
        for viewport in ((1280,720),(390,844)):
            page,shots=self.load(data,viewport,visual,measured)
            rows=self.frame(page,shots[3]["start"],viewport)["drawn"]
            items={r["s"]:r for r in rows}
            self.assertLess(items["Casi el 9 %"]["y"],items["Mayor caída entre las cinco referencias"]["y"])
            self.assertGreater(items["Casi el 9 %"]["font"],items["Mayor caída entre las cinco referencias"]["font"])
            self.assertEqual([r["color"] for r in rows if r["s"]=="−8,96 %"],["#9e1b32"])

    def test_date_projection_connects_the_trace_to_one_axis_position(self):
        for viewport in ((1280,720),(390,844)):
            with self.subTest(viewport=viewport):
                page,shots=self.load(fixture(),viewport)
                shot=shots[5]
                early=self.frame(page,shot["start"]+3,viewport)
                late=self.frame(page,shot["stop"]-3,viewport)
                axis=548 if viewport[0]==1280 else 674
                def anchor(pose):
                    return next(path["path"][1][0] for path in pose["strokes"]
                                if path["color"]=="#cfcfcf" and len(path["path"])==2
                                and path["path"][1][1]==axis and path["path"][0][0]==path["path"][1][0]
                                and path["path"][0][1]<axis-30)
                self.assertLess(anchor(early),anchor(late))
                half=8 if viewport[0]==1280 else 6
                for pose in (early,late):
                    x=anchor(pose)
                    self.assertTrue(any(path["color"]=="#333e48" and path["path"]==[[x,axis-half],[x,axis+half]]
                                        for path in pose["strokes"]))
                    self.assertFalse(any(a["y"]==axis for a in pose["arcs"]))

    def test_prior_friday_and_maturity_labels_fit_at_native_and_reduced_display_sizes(self):
        visual=recipe()
        visual[-1]["yieldUnit"]="percentage-points"
        for viewport,smaller in [((1280,720),(640,360)),((390,844),(320,693))]:
            with self.subTest(viewport=viewport):
                page,shots=self.load(fixture(),viewport,visual)
                for width,height in (viewport,smaller):
                    page.set_viewport_size({"width":width,"height":height})
                    for index in (4,6):
                        for frame in (shots[index]["start"],shots[index]["end"]-1):
                            pose=self.frame(page,frame,viewport)
                            labels={row["s"]:row for row in pose["drawn"]}
                            self.assertIn("Viernes anterior",labels)
                            self.assertEqual("Otro plazo" in labels,index==6)
                            date=next(r for r in pose["drawn"] if r["s"]=="20 nov" and r["y"] in (590,698))
                            self.assertEqual(labels["Viernes anterior"]["x"],date["x"])
                            if viewport[0]==390:
                                observed=next(r for r in pose["drawn"] if r["s"].startswith("Cierre observado"))
                                self.assertGreaterEqual(observed["box"][0]-labels["Viernes anterior"]["box"][2],12)
                                if index==6:
                                    note=next(r for r in pose["drawn"] if r["s"].startswith("Variación semanal de la tasa"))
                                    self.assertGreaterEqual(note["box"][1]-(observed["y"]+5),3)
                            if index==6:
                                self.assertLess(labels["Otro plazo"]["box"][3],labels["Tesoro a diez años"]["box"][1])
                            canvas=page.locator("canvas").bounding_box()
                            self.assertLessEqual(canvas["height"],height+.5)
                            self.assertLessEqual(canvas["width"],width+.5)
                page.close()

    def test_portrait_header_preserves_long_dates_across_a_calendar_boundary(self):
        data=fixture()
        data["semana"]="28 diciembre 2026–1 enero 2027"
        page,_=self.load(data,(390,844))
        labels={r["s"]:r for r in self.frame(page,0,(390,844))["drawn"]}
        tag,dates=labels["DATOS SINTÉTICOS"],labels[data["semana"]]
        horizontal_gap=dates["box"][0]-tag["box"][2]
        vertical_gap=dates["box"][1]-tag["box"][3]
        self.assertTrue(horizontal_gap>=10 or vertical_gap>=3)

    def test_date_and_maturity_annotations_require_a_matching_comparison(self):
        for viewport in ((1280,720),(390,844)):
            data=fixture()
            data["series"]["tlt"]["nombre"]="Fondo de muestra"
            visual=recipe()
            visual[4]["series"]="nasdaq"  # Its first observation is Monday.
            page,shots=self.load(data,viewport,visual)
            labels=lambda shot:{r["s"] for r in self.frame(page,shots[shot]["start"],viewport)["drawn"]}
            self.assertNotIn("Viernes anterior",labels(4))
            self.assertNotIn("Otro plazo",labels(6))
            page.close()
            data["inicio"]="2026-11-19"  # Thursday before a Friday market closure.
            data["series"]["oro"]["fechas"][0]="2026-11-19"
            page,shots=self.load(data,viewport,recipe())
            self.assertIn("Jueves anterior",labels(4))
            self.assertNotIn("Viernes anterior",labels(4))
            page.close()
            visual[3]["series"]="oro"  # The ten-year series also works on its own.
            page,shots=self.load(fixture(),viewport,visual)
            self.assertNotIn("Otro plazo",labels(6))
            page.close()

    def test_each_frame_highlights_an_observed_session_and_never_bridges_a_missing_date(self):
        for viewport in ((1280,720),(390,844)):
            data=fixture();page,shots=self.load(data,viewport);shot=shots[4]  # two gold observations, a week apart
            samples=page.evaluate("([a,b])=>Array.from({length:b-a},(_,i)=>inspectFrame(a+i))",[shot["start"],shot["end"]])
            l,r=(715,1193) if viewport[0]==1280 else (83,363)
            top,bottom=(215,478) if viewport[0]==1280 else (380,620)
            values=dict(zip(data["series"]["oro"]["fechas"],data["series"]["oro"]["values"]))
            for sample in samples:
                picked=sample["state"]["observation"]
                self.assertEqual(picked["value"],values[picked["date"]])
                actual_x={l,r}
                joins=[s["path"] for s in sample["strokes"] if s["color"] in ("#9e1b32","#696969") and
                       len(s["path"])==2 and {q[0] for q in s["path"]}==actual_x and all(top<=q[1]<=bottom for q in s["path"])]
                self.assertEqual(joins,[])

    def test_full_yield_title_in_both_formats_and_old_basis_point_recipe(self):
        visual=recipe()
        visual[-1]["yieldUnit"]="percentage-points"
        for viewport in ((1280,720),(390,844)):
            for difference,headline,unit,equivalent in [
                (-.23,"Bajó 0,23","puntos porcentuales","23 puntos básicos"),
                (.01,"Subió 0,01","puntos porcentuales","1 punto básico"),
                (1,"Subió 1,00","punto porcentual","100 puntos básicos"),
                (0,"Sin cambio","0 puntos porcentuales","0 puntos básicos")]:
                data=fixture()
                data["series"]["ust10"]["values"][-1]=data["series"]["ust10"]["values"][0]+difference
                page,shots=self.load(data,viewport,visual=visual)
                drawn=self.frame(page,shots[-1]["start"],viewport)["drawn"]
                by_text={r["s"]:r for r in drawn}
                self.assertTrue({headline,unit,equivalent}<=by_text.keys())
                if viewport[0]==390:
                    self.assertGreaterEqual(min(by_text[s]["font"] for s in (headline,unit)),24)
                page.close()
            page,shots=self.load(fixture(),viewport)
            self.assertIn("0 pb",[r["s"] for r in self.frame(page,shots[-1]["start"],viewport)["drawn"]])
            page.close()

    def test_custom_fund_name_and_unit_do_not_claim_tlt(self):
        data=fixture()
        data["series"]["tlt"].update(nombre="Fondo de muestra",unidad="euros por unidad")
        for viewport in ((1280,720),(390,844)):
            page,shots=self.load(data,viewport)
            for index in (0,3):
                texts=" ".join(r["s"] for r in self.frame(page,shots[index]["end"]-1,viewport)["drawn"])
                self.assertIn("Fondo de muestra",texts)
                self.assertIn("euros por unidad",texts)
                self.assertNotIn("TLT",texts)

    def test_source_footer_follows_the_series_url_and_custom_fund_on_a_real_input(self):
        data=fixture();data.pop("sintetico");data.pop("procedencia")
        for s in data["series"].values():s["fuentes"]=["https://datos.example.org/serie"]
        data["series"]["btc"]["fuentes"]=["https://api.exchange.coinbase.com/products/BTC-USD/candles"]
        data["series"]["tlt"].update(nombre="Fondo local",unidad="EUR por cuota")
        data["series"]["ust10"]["fuente_corta"]="Agencia de deuda"
        for viewport in ((1280,720),(390,844)):
            page,shots=self.load(data,viewport)
            def displayed(index):
                return " ".join(r["s"] for r in page.evaluate("f=>inspectFrame(f).drawn", shots[index]["start"]))
            self.assertIn("Fuente: Coinbase Exchange",displayed(5))
            self.assertNotIn("CoinMarketCap",displayed(5))
            self.assertIn("Fuente: datos.example.org",displayed(4))
            self.assertIn("Agencia de deuda",displayed(6))
            self.assertIn("Fondo local",displayed(0))
            self.assertNotIn("TLT",displayed(6))

    def test_sub_basis_point_rate_preserves_the_readout_endpoints_and_axis_ticks(self):
        data=fixture();data["series"]["ust10"]["values"]=[3.0,3.001,3.004]
        for viewport in ((1280,720),(390,844)):
            page,shots=self.load(data,viewport)
            rows=[r["s"] for r in self.frame(page,shots[-1]["end"]-1,viewport)["drawn"]]
            self.assertTrue({"+0,4 pb","3,004 %","3,002","3,004"}<=set(rows))

    def test_opposite_signs_and_same_signs_use_appropriate_question_and_arrows(self):
        cases=[(-.25,106,"¿Por qué suben?","Un tipo de descuento menor",1),
               (.25,94,"¿Por qué bajan?","Un tipo de descuento mayor",-1),
               (.25,106,"¿Y su precio?","Un tipo de descuento mayor",-1)]
        for viewport in ((1280,720),(390,844)):
            for close,tlt,question,discount,direction in cases:
                with self.subTest(viewport=viewport,close=close,tlt=tlt):
                    data=fixture()
                    data["series"]["ust10"]["values"][-1]=close
                    data["series"]["tlt"]["values"][-1]=tlt
                    page,shots=self.load(data,viewport)
                    query=self.frame(page,shots[1]["end"]-1,viewport)
                    self.assertIn(question,[r["s"] for r in query["drawn"]])
                    first=self.frame(page,shots[2]["start"],viewport)
                    last=self.frame(page,shots[2]["end"]-1,viewport)
                    self.assertIn(discount,[r["s"] for r in last["drawn"]])
                    for color,sign in (("#333e48",direction),("#9e1b32",-direction)):
                        x=1115 if viewport[0]==1280 else 331
                        y=lambda p: next(s["path"][-1][1] for s in p["strokes"] if s["color"]==color and s["path"][0][0]==x)
                        self.assertGreater((y(last)-y(first))*sign,0)


if __name__=="__main__":
    unittest.main()
