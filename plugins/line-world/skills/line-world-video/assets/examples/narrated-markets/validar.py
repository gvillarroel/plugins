"""Validate dated market observations and report what each close-to-close comparison covers."""
import argparse
from copy import deepcopy
from datetime import date,datetime,timedelta
from decimal import Decimal
import json
import math
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit


PRICE_IDS={"sp500","nasdaq","oro","btc","tlt"}
REQUIRED=PRICE_IDS|{"ust10"}
FACTORS={"porcentaje":Decimal(1),"fraccion":Decimal(100),"puntos_basicos":Decimal(".01")}


def fail_if(condition,message):
    if condition:raise ValueError(message)


def headline_start(first, last):
    """Label a standard Friday-close comparison with the Monday of its workweek."""
    if last.weekday() == 4 and last - first == timedelta(days=7):
        return last - timedelta(days=4)
    return first


def dates_in(a,b):
    return [a+timedelta(days=i) for i in range((b-a).days+1)]


def iso_days(raw,key):
    try:
        if not isinstance(raw,list):raise TypeError
        return [date.fromisoformat(v).isoformat() for v in raw]
    except (ValueError,TypeError) as exc:raise ValueError(f"{key}: invalid session date.") from exc


def legacy_days(raw,calendar,key):
    try:
        if not isinstance(raw,list) or any(type(d) is not int for d in raw):raise TypeError
        return [calendar[d] for d in raw]
    except (TypeError,KeyError) as exc:raise ValueError(f"{key}: invalid session date in dias.") from exc


def numbers(values,dates,key,kind):
    for d,v in zip(dates,values):
        fail_if(type(v) not in (int,float) or not math.isfinite(v),
                f"{key} ({d}): supply a finite observation or omit the unquoted session.")
        fail_if(kind=="precio" and v<=0,f"{key} ({d}): price must be greater than zero.")


def usable_url(value):
    if not isinstance(value,str) or any(c.isspace() for c in value):return False
    try:
        parts=urlsplit(value)
        return parts.scheme=="https" and bool(parts.hostname)
    except ValueError:return False


def read_observations(series,key):
    rows=series["observaciones"]
    fail_if(not isinstance(rows,list) or any(not isinstance(r,dict) or "fecha" not in r or "valor" not in r for r in rows),
            f"{key}: observaciones requiere fecha y valor por registro.")
    last=None
    for row in rows:
        if "cierre" not in row:continue
        try:
            raw=row["cierre"]
            if not isinstance(raw,str) or "T" not in raw:raise ValueError
            ts=datetime.fromisoformat(raw)
            if ts.utcoffset() is None or (last is not None and ts<=last):raise ValueError
        except (TypeError,ValueError) as exc:
            raise ValueError(f"{key} ({row['fecha']}): cierre debe ser un instante ISO con zona y en orden.") from exc
        last=ts
    return iso_days([r["fecha"] for r in rows],key),[r["valor"] for r in rows]


def series_dates(series,data,calendar,key):
    candidates=[]
    if "observaciones" in series:
        declared,raw=read_observations(series,key)
        numbers(raw,declared,key,series["tipo"])
        candidates.append(("observaciones",declared))
        if "values" in series:
            fail_if(raw!=series["values"],f"{key}: observaciones y values discrepan.")
        else:series["values"]=raw
    if "fechas" in series:candidates.append(("fechas",iso_days(series["fechas"],key)))
    if "dias" in series:candidates.append(("dias",legacy_days(series["dias"],calendar,key)))
    if not candidates and "dias" in data:candidates.append(("dias globales",legacy_days(data["dias"],calendar,key)))
    fail_if(not candidates,f"{key}: no se declararon las fechas de sesión.")
    name,days=candidates[0]
    for other,dates in candidates[1:]:
        fail_if(dates!=days,f"{key}: las fechas de {name} y {other} discrepan.")
    return days


def standard_rate(series,key):
    unit=series["unidad"].casefold()
    declared=series.get("escala_tasa")
    bps=bool(re.search(r"\b(?:pb|bps?|puntos? b[áa]sicos?|basis points?)\b",unit))
    fraction=("fracción" in unit or "fraccion" in unit or unit.strip() in ("ratio","decimal","proporción"))
    unit_scale="puntos_basicos" if bps else "fraccion" if fraction else None
    if unit_scale and declared!=unit_scale:
        raise ValueError(f"{key}: unidad '{series['unidad']}' requiere escala_tasa='{unit_scale}' antes de calcular puntos básicos.")
    expressed_percent=any(mark in unit for mark in ("%","por ciento","porcentaje","percent"))
    fail_if(not expressed_percent and declared is None,f"{key}: identifica el rendimiento en % o declara escala_tasa.")
    fail_if(expressed_percent and declared not in (None,"porcentaje"),f"{key}: la unidad de origen en % contradice escala_tasa.")
    if "unidad_eje" in series and not any(mark in series["unidad_eje"].casefold() for mark in ("%","por ciento","porcentaje","percent")):
        raise ValueError(f"{key}: unidad_eje debe identificar el rendimiento normalizado en porcentaje.")
    if declared is None:return
    fail_if(not isinstance(declared,str) or declared not in FACTORS,f"{key}: escala_tasa debe ser porcentaje, fraccion o puntos_basicos.")
    if declared=="porcentaje" and expressed_percent:return
    factor=FACTORS[declared]
    raw=series["values"]
    values=[float(Decimal(str(n))*factor) for n in raw]
    numbers(values,series["fechas"],key,"rendimiento")
    series.update(values=values,escala_tasa="porcentaje",unidad="rendimiento anual, %",
                  tasa_origen={"escala":declared,"unidad":series["unidad"],"values":raw})
    if "observaciones" in series:
        for row,value in zip(series["observaciones"],values):row["valor"]=value


def normalize(data,partial=False):
    fail_if(not isinstance(data,dict),"Los datos deben ser un objeto JSON.")
    data=deepcopy(data)
    try:a,b=(date.fromisoformat(data[k]) for k in ("inicio","fin"))
    except (ValueError,KeyError,TypeError) as exc:raise ValueError("inicio y fin deben ser fechas ISO.") from exc
    data.update(inicio=a.isoformat(),fin=b.isoformat())
    fail_if(not a<b or (b-a).days>21,"Provide the prior and current weekly closing dates.")
    all_dates=dates_in(a,b);calendar={d.day:d.isoformat() for d in all_dates}
    curves=data.get("series")
    fail_if(not isinstance(curves,dict) or not curves,"Missing series.")
    if not partial:fail_if(not REQUIRED.issubset(curves),"Missing a weekly benchmark.")
    if not partial:
        for field in ("mercado","semana"):
            fail_if(not isinstance(data.get(field),str) or not data[field].strip(),"Falta el encabezado "+field+".")
    order=data.get("orden")
    if order is not None:
        fail_if(not isinstance(order,list) or len(order)!=5 or not all(isinstance(k,str) for k in order) or set(order)!=PRICE_IDS,
                "orden must contain each of the five price series once.")
    if "descripcionUniverso" in data:
        desc=data["descripcionUniverso"]
        fail_if(not isinstance(desc,list) or len(desc)!=2 or not all(isinstance(line,str) and line.strip() for line in desc),
                "Provide two short lines describing the comparison universe.")
    synthetic=data.get("sintetico",False)
    fail_if(type(synthetic) is not bool,"sintetico debe ser verdadero o falso.")
    fail_if(synthetic and (not isinstance(data.get("procedencia"),str) or not data["procedencia"].strip()),"Declare the fixture's origin.")
    for key,series in curves.items():
        fail_if(not isinstance(series,dict),f"{key}: expected a series object.")
        for field in ("nombre","unidad","tipo"):
            fail_if(not isinstance(series.get(field),str) or not series[field].strip(),f"{key}: falta {field}.")
        kind=series["tipo"]
        expected="rendimiento" if key=="ust10" else "precio" if key in PRICE_IDS else kind
        fail_if(expected!=kind or kind not in ("precio","rendimiento"),f"{key}: expected tipo={expected}.")
        urls=series.get("fuentes",[])
        fail_if(not isinstance(urls,list) or not all(usable_url(u) for u in urls) or (not synthetic and not urls),
                f"{key} needs the source links for its observed closes.")
        for field in ("zona_horaria","convencion_cierre","unidad_eje","fuente_corta"):
            if field in series:fail_if(not isinstance(series[field],str) or not series[field].strip(),f"{key}: {field} necesita texto.")
        ds=series_dates(series,data,calendar,key)
        fail_if(any(not a.isoformat()<=d<=b.isoformat() for d in ds),f"{key}: date outside the observed week.")
        values=series.get("values")
        fail_if(not isinstance(values,list) or len(ds)!=len(values) or len(ds)<2 or ds!=sorted(set(ds)),
                f"{key}: supply at least two dated closes in chronological order.")
        numbers(values,ds,key,kind)
        series["fechas"]=ds
        if kind=="rendimiento":standard_rate(series,key)
        elif "escala_tasa" in series:raise ValueError(f"{key}: escala_tasa no se aplica a precios.")
    return data


def report(data):
    all_days={d.isoformat() for d in dates_in(date.fromisoformat(data["inicio"]),date.fromisoformat(data["fin"]))}
    rows={}
    for key,s in data["series"].items():
        ds=s["fechas"];first,last=(Decimal(str(v)) for v in (s["values"][0],s["values"][-1]))
        rate=s["tipo"]=="rendimiento"
        change=100*(last-first) if rate else 100*(last/first-1)
        rows[key]={"fechasObservadas":ds,"sinObservacion":sorted(all_days-set(ds)),"inicioObservado":ds[0],"finObservado":ds[-1],
                   "valorInicial":float(first),"valorFinal":float(last),"unidadObservada":s["unidad"],
                   "variacion":float(change),"unidadVariacion":"pb" if rate else "%","fuentes":s.get("fuentes",[])}
        for field in ("zona_horaria","convencion_cierre"):
            if field in s:rows[key][field]=s[field]
    return {"ok":True,"referenciasCompletas":REQUIRED.issubset(rows),"sintetico":data.get("sintetico",False),
            "mismosExtremosObservados":len({(s["inicioObservado"],s["finObservado"]) for s in rows.values()})==1,"series":rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("datos",type=Path)
    p.add_argument("--parcial",action="store_true",help="Revisa las series suministradas antes de reunir las seis del episodio.")
    p.add_argument("--out",type=Path,help="Crea una carpeta nueva con datos.json e informe.json.")
    a=p.parse_args()
    try:
        data=normalize(json.loads(a.datos.read_text(encoding="utf-8-sig")),a.parcial);audit=report(data)
        if not a.out:print(json.dumps(audit,ensure_ascii=False,indent=2));return
        dest=a.out.resolve()
        if dest.exists():raise ValueError("Elige un directorio de salida nuevo.")
        dest.parent.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
            folder=Path(tmp)/"validado";folder.mkdir()
            for name,body in (("datos.json",data),("informe.json",audit)):
                (folder/name).write_text(json.dumps(body,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
            folder.rename(dest)
    except (OSError,ValueError,TypeError) as exc:p.exit(1,"validar: "+str(exc)+"\n")


if __name__=="__main__":main()
