"""Exercise independent calendars, declared close times and yield scales without filling missing observations."""
from copy import deepcopy
import unittest

from validar import normalize,report


FRIDAY="2024-11-22"
LAST="2024-11-29"
TREASURY_DATES=[FRIDAY,"2024-11-25","2024-11-26","2024-11-27",LAST]
COIN_DATES=[f"2024-11-{day}" for day in range(22,30)]


def window():
    return {"inicio":FRIDAY,"fin":LAST,"series":{
        "ust10":{"nombre":"Tesoro a 10 años","unidad":"rendimiento anual, %","tipo":"rendimiento",
                 "fuentes":["https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview?data=daily_treasury_yield_curve&field_tdr_date_value_month=202411"],
                 "fechas":TREASURY_DATES.copy(),"values":[4.41,4.27,4.30,4.25,4.18]},
        "btc":{"nombre":"Bitcoin","unidad":"USD por BTC","tipo":"precio","fuentes":["https://api.exchange.coinbase.com/products/BTC-USD/candles"],
               "fechas":COIN_DATES.copy(),"values":[99024.03,97778.77,98028.18,93000.01,91929.54,95951.19,95665.53,97490.56],
               "zona_horaria":"UTC","convencion_cierre":"Última operación de la vela diaria en Coinbase Exchange."}}}


class MarketData(unittest.TestCase):
    def test_real_four_session_week_and_weekend_btc_preserve_only_observed_closes(self):
        data=window();normalized=normalize(data,partial=True);r=report(normalized)
        self.assertEqual(normalized,data)
        self.assertFalse(r["referenciasCompletas"])
        self.assertEqual(r["series"]["ust10"]["sinObservacion"],["2024-11-23","2024-11-24","2024-11-28"])
        self.assertEqual(r["series"]["ust10"]["variacion"],-23)
        self.assertEqual(r["series"]["btc"]["sinObservacion"],[])
        self.assertEqual(r["series"]["btc"]["fechasObservadas"],COIN_DATES)
        with self.assertRaisesRegex(ValueError,"Missing a weekly benchmark"):normalize(data)

    def test_empty_declared_calendar_never_uses_other_series_or_parent_defaults(self):
        data=window();data["dias"]=[22,25,26,27,29];series=data["series"]["ust10"];series["fechas"]=[]
        with self.assertRaisesRegex(ValueError,"at least two"):normalize(data,True)
        series.pop("fechas");self.assertEqual(normalize(data,True)["series"]["ust10"]["fechas"],TREASURY_DATES)
        series["fechas"]=TREASURY_DATES;series["dias"]=[22,25,26,27,28]
        with self.assertRaisesRegex(ValueError,"discrepan"):normalize(data,True)
        series.pop("fechas");series["dias"]=[True,25,26,27,29]
        with self.assertRaisesRegex(ValueError,"invalid session date"):normalize(data,True)

    def test_partial_dates_midnight_and_declared_early_close_remain_independent(self):
        data=window();series=data["series"]["ust10"]
        series["fechas"]=series["fechas"][1:];series["values"]=series["values"][1:]
        self.assertFalse(report(normalize(data,True))["mismosExtremosObservados"])
        # A deliberately synthetic exchange example demonstrates storage of an actual local instant.
        data={"inicio":FRIDAY,"fin":LAST,"sintetico":True,"procedencia":"Prueba de horarios", "series":{
            "sp500":{"nombre":"Índice de ensayo","unidad":"puntos","tipo":"precio","zona_horaria":"America/New_York",
                     "observaciones":[{"fecha":FRIDAY,"valor":100,"cierre":FRIDAY+"T16:00:00-05:00"},
                                      {"fecha":LAST,"valor":101,"cierre":LAST+"T13:00:00-05:00"}]}}}
        s=normalize(data,True)["series"]["sp500"]
        self.assertEqual(s["fechas"],[FRIDAY,LAST]);self.assertEqual(s["values"],[100,101])
        self.assertEqual(s["observaciones"][-1]["cierre"],LAST+"T13:00:00-05:00")
        data["series"]["sp500"]["observaciones"][1]["cierre"]=LAST+"T13:00:00"
        with self.assertRaisesRegex(ValueError,"instante ISO"):normalize(data,True)

    def test_percent_ratio_and_basis_points_give_the_same_annual_rate(self):
        for scale,unit,values in (("fraccion","fracción anual",[.0441,.0427,.043,.0425,.0418]),
                                  ("puntos_basicos","puntos básicos",[441,427,430,425,418])):
            data=window();series=data["series"]["ust10"];series.update(unidad=unit,values=values)
            with self.assertRaisesRegex(ValueError,"requiere escala_tasa"):normalize(data,True)
            series["escala_tasa"]=scale;before=deepcopy(data)
            out=normalize(data,True);actual=out["series"]["ust10"]
            self.assertEqual(data,before)
            self.assertEqual(actual["values"],[4.41,4.27,4.3,4.25,4.18])
            self.assertEqual(actual["tasa_origen"]["values"],values);self.assertEqual(report(out)["series"]["ust10"]["variacion"],-23)
            self.assertEqual(normalize(out,True),out)

    def test_invalid_source_or_structured_values_fail(self):
        data=window();series=data["series"]["btc"]
        for bad in ("https://", "https://ausente ejemplo.org", [], "https://example.org"):
            series["fuentes"]=bad if isinstance(bad,list) or bad=="https://example.org" else [bad]
            with self.assertRaisesRegex(ValueError,"source links"):normalize(data,True)
        series["fuentes"]=["https://www.coinbase.com"]
        series["observaciones"]=[{"fecha":d,"valor":v} for d,v in zip(series["fechas"],series["values"])]
        series["observaciones"][0]["valor"]=None
        with self.assertRaisesRegex(ValueError,"finite observation"):normalize(data,True)
        series["observaciones"][0]["valor"]=10
        with self.assertRaisesRegex(ValueError,"discrepan"):normalize(data,True)

    def test_an_opaque_yield_unit_cannot_silently_become_a_percent(self):
        data=window();rate=data["series"]["ust10"];rate["unidad"]="unidades"
        with self.assertRaisesRegex(ValueError,"escala_tasa"):normalize(data,True)
        rate["escala_tasa"]="porcentaje"
        normalized=normalize(data,True)["series"]["ust10"]
        self.assertEqual(normalized["unidad"],"rendimiento anual, %")
        self.assertEqual(normalized["tasa_origen"]["unidad"],"unidades")
        rate["unidad"]="Porcentaje anual";rate["escala_tasa"]="fraccion"
        with self.assertRaisesRegex(ValueError,"contradice"):normalize(data,True)
        rate.pop("escala_tasa");rate["unidad_eje"]="USD"
        with self.assertRaisesRegex(ValueError,"unidad_eje"):normalize(data,True)


if __name__=="__main__":unittest.main()
