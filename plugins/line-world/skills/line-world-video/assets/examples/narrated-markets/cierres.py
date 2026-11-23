"""Retrieve source rows independently, then compare a frozen receipt with an episode offline."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import html
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import validar


TREASURY = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xmlview"
GOLD = "https://www.investing.com/currencies/xau-usd-historical-data"
ISHARES = "https://www.ishares.com/us/products/239454/ishares-20-year-treasury-bond-etf"
CBOE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/SPX_History.csv"
CMC = "https://coinmarketcap.com/historical/"
CMC_OHLC = "https://api.coinmarketcap.com/data-api/v3/cryptocurrency/historical"
PRIMARY = {"sp500":["fred","cboe"],"nasdaq":["comp"],"tlt":["tlt"],"oro":["xau"],
           "btc":["btc-ohlc"],"ust10":["tesoro"]}
UNIT = {"sp500":"puntos de índice de precios","nasdaq":"puntos de índice","tlt":"USD por participación, cierre sin ajustar",
        "oro":"USD por onza troy, XAU/USD al contado","btc":"USD por BTC, cierre UTC","ust10":"% anual, curva par a diez años"}
METHOD = {"sp500":"cierre de la sesión del índice","nasdaq":"cierre de la sesión del índice",
          "tlt":"precio de cierre de la participación en bolsa","oro":"columna Price de la sesión diaria del proveedor",
          "btc":"timeClose por día natural, a las 23:59:59.999 UTC","ust10":"observación diaria de la curva par del Tesoro, plazo de diez años"}
SECONDARY = {"sp500":["cboe"],"oro":["xau-es"],"btc":["btc-snapshot"],"tlt":["ishares-cierre"]}
LABELS = {"sp500":"S&P 500","nasdaq":"Nasdaq Composite","oro":"Oro al contado","btc":"Bitcoin",
          "tlt":"Bonos del Tesoro","ust10":"Tesoro a 10 años"}
UNITS = {"sp500":"puntos","nasdaq":"puntos","oro":"USD por onza troy","btc":"USD por BTC",
         "tlt":"USD por participación de TLT","ust10":"rendimiento anual, %"}
MONTHS = ("enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre")


def write_new(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2)+"\n"
    # Publish only after the complete payload exists. A concurrent or existing destination wins.
    with tempfile.TemporaryDirectory(dir=path.parent) as scratch:
        temp=Path(scratch)/"candidate"
        temp.write_text(data,encoding="utf-8")
        try:
            os.link(temp,path)
        except FileExistsError:
            raise
        except OSError:
            # Volumes without hard-link support still enforce exclusive creation.
            with path.open("x",encoding="utf-8") as result:
                try:result.write(data)
                except BaseException:
                    result.close();path.unlink(missing_ok=True);raise


def fetch(url):
    req=Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"*/*","Accept-Language":"en-US,en;q=0.9"})
    with urlopen(req,timeout=20) as r:
        body=r.read(12*1024**2+1)
        if len(body)>12*1024**2:raise ValueError("Response exceeds 12 MiB")
        return body,{"url":r.geturl(),"http":r.status,"fetchedUtc":datetime.now(timezone.utc).isoformat(),
                     "contentType":r.headers.get("Content-Type"),"httpDate":r.headers.get("Date"),
                     "originalBytes":len(body),"responseSha256":hashlib.sha256(body).hexdigest()}


def day(s, fmt):
    return datetime.strptime(s,fmt).date().isoformat()


class TableRows(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=="tr":self.row=[]
        if self.row is not None and tag in ("td","th"):self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ("td","th") and self.row is not None and self.cell is not None:
            self.row.append(" ".join(" ".join(self.cell).split()));self.cell=None
        if tag=="tr" and self.row is not None:self.rows.append(self.row);self.row=None;self.cell=None


def extract(key,text):
    rows={}
    if key in ("fred","cboe"):
        for row in csv.DictReader(io.StringIO(text)):
            if key=="fred":
                val=row["SP500"]
                if val not in ("","."):rows[row["observation_date"]]=(val,row)
            else:rows[day(row["DATE"],"%m/%d/%Y")]=(row["SPX"],row)
    elif key in ("comp","tlt"):
        data=json.loads(text)["data"]
        if not data or data["symbol"]!={"comp":"COMP","tlt":"TLT"}[key]:raise ValueError("Missing expected symbol")
        records=data["tradesTable"]["rows"]
        if int(data["totalRecords"])!=len(records):raise ValueError("Nasdaq devolvió una página incompleta.")
        for row in records:
            rows[day(row["date"],"%m/%d/%Y")]=(row["close"].replace(",",""),row)
        if len(rows)!=len(records):raise ValueError("Nasdaq devolvió fechas repetidas.")
    elif key in ("xau","xau-es"):
        table=TableRows();table.feed(text);spanish=key=="xau-es"
        for row in table.rows:
            if len(row)<5:continue
            try:d=day(row[0],"%d.%m.%Y" if spanish else "%b %d, %Y")
            except ValueError:continue
            value=row[1].replace(".","").replace(",",".") if spanish else row[1].replace(",","")
            rows[d]=(value,dict(zip(["date","price","open","high","low"],row[:5])))
    elif key.split("/")[0]=="tesoro":
        for node in ET.fromstring(text).iter():
            if node.tag.split("}")[-1]!="properties":continue
            values={x.tag.split("}")[-1]:x.text for x in node}
            if values.get("BC_10YEAR"):
                rows[values["NEW_DATE"][:10]]=(values["BC_10YEAR"],{k:values[k] for k in ("Id","NEW_DATE","BC_10YEAR")})
    elif key=="btc-ohlc":
        entry=json.loads(text,parse_float=str)["data"]
        if entry["id"]!=1 or entry["symbol"]!="BTC":raise ValueError("Unexpected cryptocurrency")
        for q in entry["quotes"]:
            raw=q["quote"]
            if (q["timeClose"]!=raw["timestamp"] or not q["timeClose"].endswith("T23:59:59.999Z")
                    or not q["timeOpen"].endswith("T00:00:00.000Z") or str(raw["name"])!="2781"):
                raise ValueError("Unexpected clock or quote currency")
            rows[q["timeClose"][:10]]=(str(raw["close"]),{"timeOpen":q["timeOpen"],"timeClose":q["timeClose"],
                "quote":{k:raw[k] for k in ("name","open","high","low","close","timestamp")}})
    elif key.startswith("btc-snapshot/"):
        d=key.split("/")[1]
        meta=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',text,re.S)[1])["props"]["pageProps"]
        if meta["dateWithHyphens"]!=d:raise ValueError("Historical snapshot date mismatch")
        table=TableRows();table.feed(text)
        for row in table.rows:
            if len(row)>5 and row[2]=="BTC" and "Bitcoin" in row[1] and row[4].startswith("$"):
                rows[d]=(row[4][1:].replace(",",""),{"date":d,"symbol":row[2],"price":row[4]});break
    elif key=="ishares-cierre":
        m=re.search(r'"closingPrice":(\{"visible":true,[^{}]+\})',html.unescape(text))
        obj=json.loads(m[1])
        if obj["label"]!="Closing Price" or obj["prefix"]!="$":raise ValueError("Unexpected fund quote")
        rows[day(obj["formattedAsOfDate"],"%b %d, %Y")]=(obj["formattedValue"],{k:obj[k] for k in ("name","label","formattedValue","formattedAsOfDate","prefix")})
    elif key=="ishares-nav":
        section=re.search(r'<ss:Worksheet ss:Name="Historical">(.+?)</ss:Worksheet>',text,re.S)[1]
        records=re.findall(r'<ss:Row[^>]*>(.*?)</ss:Row>',section,re.S)
        def cells(s):return re.findall(r'<ss:Data[^>]*>([^<]+)',s,re.S)
        cols=cells(records[0]);i=cols.index("NAV per Share")
        for rec in records[1:]:
            r=cells(rec)
            if len(r)>i:
                rows[day(r[0],"%b %d, %Y")]=(r[i],{cols[0]:r[0],cols[i]:r[i]})
    if not rows:raise ValueError("The provider returned no recognizable source rows")
    return rows


def source_urls(start,end):
    def ts(d,t):return int(datetime.combine(d,t,tzinfo=timezone.utc).timestamp())
    a,b=start.isoformat(),end.isoformat()
    nas="https://api.nasdaq.com/api/quote/{}/historical?assetclass={}&fromdate="+a+"&todate="+b
    urls={"fred":"https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({"coed":b,"cosd":a,"id":"SP500"}),
          "cboe":CBOE,"comp":nas.format("COMP","index"),"tlt":nas.format("TLT","etf"),
          "tesoro":TREASURY+"?"+urlencode({"data":"daily_treasury_yield_curve","field_tdr_date_value_month":start.strftime("%Y%m")}),
          "xau":GOLD,"xau-es":GOLD.replace("www.","es."),"btc-ohlc":CMC_OHLC+"?"+urlencode({"id":1,"convertId":2781,
          "timeStart":ts(start,time(0)), "timeEnd":ts(end,time(23,59,59))}),"ishares-cierre":ISHARES,
          "ishares-nav":"https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?"+
          urlencode({"appType":"PRODUCT_PAGE","appSubType":"ISHARES","targetSite":"us-ishares","locale":"en_US","portfolioId":239454,"component":"fundDownload","userType":"individual"})}
    if start.month!=end.month or start.year!=end.year:
        urls["tesoro/"+end.strftime("%Y%m")]=TREASURY+"?"+urlencode({"data":"daily_treasury_yield_curve",
                                                                  "field_tdr_date_value_month":end.strftime("%Y%m")})
    for i in range((end-start).days+1):
        d=start+timedelta(days=i);urls["btc-snapshot/"+d.isoformat()]=CMC+d.strftime("%Y%m%d")+"/"
    return urls


def collect(start,end,out):
    if out.exists():raise ValueError("Choose a new receipt file for a fresh capture.")
    if not 0<(end-start).days<=21:
        raise ValueError("Indica dos fechas ordenadas separadas por un máximo de 21 días.")
    urls=source_urls(start,end)
    def capture(item):
        key,url=item
        record={"url":url,"attemptedUtc":datetime.now(timezone.utc).isoformat()}
        try:
            body,record=fetch(url);rows=extract(key,body.decode("utf-8-sig"))
            record["rows"]={d:{"value":v,"originalRow":raw} for d,(v,raw) in sorted(rows.items())
                            if start.isoformat()<=d<=end.isoformat()}
            record["observedDates"]=sorted(record["rows"])
            record["status"]="rows" if record["rows"] else "no observations in interval"
        except Exception as err:
            record.update(status="unavailable",error=str(err),rows={})
            if getattr(err,"code",None):record["http"]=err.code
        return key,record
    with ThreadPoolExecutor(max_workers=5) as workers:
        providers=dict(workers.map(capture,urls.items()))
    series={k:{"unit":UNIT[k],"calendar":METHOD[k],"sources":keys_for(k,providers)} for k in PRIMARY}
    write_new(out,{"version":1,"start":str(start),"end":str(end),"series":series,"providers":providers})
    missing=[k for k,v in providers.items() if v["status"]!="rows"]
    print(f"Recibo guardado en {out}. Fuentes sin filas en el intervalo: {', '.join(missing) or 'ninguna'}.")
    return int(any(not any(providers[k]["rows"] for k in metadata["sources"]) for metadata in series.values()))


def add_public_tables(prior, english, spanish, out):
    """Import factual rows copied from the public daily XAU/USD table when HTTP is refused."""
    if out.exists():raise ValueError("Choose a new receipt path.")
    receipt=json.loads(prior.read_text(encoding="utf-8"))
    for key,path in (("xau",english),("xau-es",spanish)):
        if path is None:continue
        attempt=receipt["providers"][key]
        data=path.read_bytes()
        rows={}
        for r in csv.DictReader(io.StringIO(data.decode("utf-8-sig"))):
            d=day(r["Date"], "%b %d, %Y" if key=="xau" else "%d.%m.%Y")
            if d in rows or not receipt["start"]<=d<=receipt["end"]:raise ValueError("Duplicate or out-of-range table row.")
            value=r["Price"].replace(",","") if key=="xau" else r["Price"].replace(".","").replace(",",".")
            Decimal(value)
            rows[d]={"value":value,"originalRow":r}
        if not rows:raise ValueError(f"{key}: el CSV público no contiene observaciones.")
        for d,previous in attempt.get("rows",{}).items():
            if d not in rows or Decimal(previous["value"])!=Decimal(rows[d]["value"]):
                raise ValueError(f"{key} {d}: la tabla importada contradice u omite la observación del recibo anterior.")
        receipt["providers"][key]={"url":attempt["url"],"status":"rows","retrieval":"public daily HTML table captured through web reader",
            "extractFile":path.name,"extractSha256":hashlib.sha256(data).hexdigest(),"importedUtc":datetime.now(timezone.utc).isoformat(),
            "httpAttempt":{k:v for k,v in attempt.items() if k!="rows"},"observedDates":sorted(rows),"rows":dict(sorted(rows.items()))}
    write_new(out,receipt)


def load_receipt(path):
    return validate_receipt(json.loads(path.read_bytes()))


def validate_receipt(obj):
    a,b=(date.fromisoformat(obj[k]) for k in ("start","end"))
    if not 0<(b-a).days<=21 or not isinstance(obj.get("providers"),dict):raise ValueError("Recibo de fechas no válidas.")
    for series,meta in obj.get("series",{}).items():
        if series not in UNIT or meta.get("unit")!=UNIT[series] or meta.get("calendar")!=METHOD[series]:
            raise ValueError(f"{series}: unidad o calendario del recibo incompatible.")
    for k,p in obj["providers"].items():
        if not isinstance(p,dict) or not isinstance(p.get("rows"),dict) or not validar.usable_url(p.get("url")):
            raise ValueError(f"{k}: recibo sin filas o URL HTTPS identificable.")
        if "observedDates" in p and sorted(p["rows"])!=p["observedDates"]:raise ValueError(f"{k}: faltan o sobran filas respecto a la captura.")
        if any(not a<=date.fromisoformat(d)<=b for d in p["rows"]):raise ValueError(f"{k}: fecha fuera del intervalo.")
    return obj


def keys_for(series, providers):
    return [k for k in [*PRIMARY[series],*(sorted(p for p in providers if p.startswith("tesoro/")) if series=="ust10" else [])]
            if k in providers]


def extract_episode(receipt, out, sessions=None):
    if out.exists():raise FileExistsError(f"La salida ya existe: {out}")
    data=load_receipt(receipt);providers=data["providers"]
    a,b=(date.fromisoformat(data[s]) for s in ("start","end"))
    calendar=json.loads(sessions.read_text(encoding="utf-8-sig")) if sessions else {}
    if not isinstance(calendar,dict) or set(calendar)-set(PRIMARY):
        raise ValueError("El calendario debe vincular cada serie identificada a sus fechas de observación.")
    daily={d.isoformat() for d in validar.dates_in(a,b)}
    first=validar.headline_start(a,b)
    start=str(first.day)
    if (first.year, first.month) != (b.year, b.month):
        start += " " + MONTHS[first.month-1]
    if first.year != b.year:
        start += " " + str(first.year)
    result={"inicio":str(a),"fin":str(b),"semana":f"{start}–{b.day} {MONTHS[b.month-1]} {b.year}","mercado":"EE. UU.","series":{}}
    for series in PRIMARY:
        keys=keys_for(series,providers)
        dates=sorted(set().union(*(providers[k]["rows"].keys() for k in keys)))
        if len(dates)<2:raise ValueError(f"{series}: faltan observaciones de sus proveedores de cierre.")
        if series=="btc" and set(dates)!=daily:raise ValueError(f"btc: faltan cierres UTC para {sorted(daily-set(dates))}")
        if series in calendar:
            stated=validar.iso_days(calendar[series],series)
            if sorted(set(stated))!=stated or dates!=stated:raise ValueError(f"{series}: las fechas del proveedor y del calendario difieren.")
        elif dates[0]!=str(a) or dates[-1]!=str(b):
            raise ValueError(f"{series}: falta un extremo solicitado. Revisa el recibo; una sesión cerrada se declara con --sessions.")
        values=[];used=[]
        for d in dates:
            candidates=[k for k in keys if d in providers[k]["rows"]]
            key=candidates[0];value=source_value(providers,key,d)
            variants=[p+"/"+d if p=="btc-snapshot" else p for p in SECONDARY.get(series,[])]
            for other in set(candidates[1:]+variants):
                if other in providers and d in providers[other]["rows"] and source_value(providers,other,d)!=value:
                    raise ValueError(f"{series} {d}: los valores de {key} y {other} discrepan.")
            values.append(float(value))
            if providers[key]["url"] not in used:used.append(providers[key]["url"])
        result["series"][series]={"nombre":LABELS[series],"unidad":UNITS[series],"tipo":"rendimiento" if series=="ust10" else "precio",
            "fechas":dates,"values":values,"fuentes":used,"convencion_cierre":METHOD[series]}
        if series=="btc":result["series"][series]["zona_horaria"]="UTC"
    stock_dates=result["series"]["sp500"]["fechas"]
    for series in ("nasdaq","tlt"):
        if result["series"][series]["fechas"]!=stock_dates and not {series,"sp500"}<=calendar.keys():
            raise ValueError(f"{series}: el calendario difiere del S&P 500. Revisa ambas fuentes y declara sus fechas en --sessions.")
    write_new(out,validar.normalize(result))
    print(f"Datos de seis series publicados en {out} a partir del recibo congelado.")


def source_value(providers, key, d):
    row=providers[key]["rows"][d];raw=row["originalRow"]
    if key=="btc-ohlc":
        quote=raw["quote"]
        if (str(quote["name"])!="2781" or raw["timeOpen"]!=d+"T00:00:00.000Z" or
                raw["timeClose"]!=d+"T23:59:59.999Z" or quote["timestamp"]!=raw["timeClose"]):
            raise ValueError(f"{key} {d}: la moneda o el reloj diario UTC no corresponden.")
        v=Decimal(quote["close"])
    elif key in ("tlt","comp"):
        if "close" not in raw or day(raw["date"],"%m/%d/%Y")!=d:raise ValueError(f"{key} {d}: falta el cierre de mercado fechado.")
        v=Decimal(raw["close"].replace(",",""))
    elif key=="fred":
        if raw["observation_date"]!=d:raise ValueError(f"{key} {d}: fecha original distinta.")
        v=Decimal(raw["SP500"])
    elif key=="cboe":
        if day(raw["DATE"],"%m/%d/%Y")!=d:raise ValueError(f"{key} {d}: fecha original distinta.")
        v=Decimal(raw["SPX"])
    elif key.startswith("tesoro"):
        if raw["NEW_DATE"][:10]!=d:raise ValueError(f"{key} {d}: fecha original distinta.")
        v=Decimal(raw["BC_10YEAR"])
    elif key.startswith("xau"):
        text=raw.get("Price",raw.get("price",""))
        if day(raw.get("Date",raw.get("date","")),"%d.%m.%Y" if key=="xau-es" else "%b %d, %Y")!=d:
            raise ValueError(f"{key} {d}: fecha original distinta.")
        v=Decimal(text.replace(".","").replace(",",".") if key=="xau-es" else text.replace(",",""))
    elif key.startswith("btc-snapshot/"):
        if raw["date"]!=d or raw["symbol"]!="BTC" or not raw["price"].startswith("$"):
            raise ValueError(f"{key} {d}: instantánea sin BTC/USD fechado.")
        v=Decimal(raw["price"][1:].replace(",",""))
    elif key=="ishares-cierre":
        if raw["label"]!="Closing Price" or raw["prefix"]!="$" or day(raw["formattedAsOfDate"],"%b %d, %Y")!=d:
            raise ValueError(f"{key}: se esperaba el precio de cierre fechado en USD.")
        v=Decimal(raw["formattedValue"])
    else:raise ValueError(f"Fuente incompatible con los cierres: {key}")
    if not v.is_finite() or v!=Decimal(row["value"]):raise ValueError(f"{key} {d}: la observación difiere de la fila original.")
    return v.quantize(Decimal(".01"),rounding=ROUND_HALF_UP) if key.startswith("btc") else v


def check_episode_units(markets):
    for key,expected in UNITS.items():
        s=markets["series"][key];unit=s["unidad"].casefold()
        if key in ("sp500","nasdaq"):valid=unit in ("puntos","puntos de índice","puntos del índice")
        elif key=="ust10":valid=s.get("escala_tasa","porcentaje")=="porcentaje" and "%" in unit
        else:
            subject={"tlt":("participación","acción","share"),"btc":("btc","bitcoin"),"oro":("onza troy","oz troy","/oz")}[key]
            valid="usd" in unit and any(w in unit for w in subject) and not any(w in unit for w in ("nav","liquidativo","futuros"))
        if not valid:raise ValueError(f"{key}: la unidad {s['unidad']!r} no corresponde a {expected}.")


def compare_rows(episode, receipt):
    episode_bytes,receipt_bytes=episode.read_bytes(),receipt.read_bytes()
    markets=validar.normalize(json.loads(episode_bytes))
    check_episode_units(markets)
    evidence=validate_receipt(json.loads(receipt_bytes))
    if [markets["inicio"],markets["fin"]]!=[evidence["start"],evidence["end"]]:
        raise ValueError("The receipt dates differ from the episode.")
    checks=[]
    for series in PRIMARY:
        info=markets["series"][series]; dates=info["fechas"]
        if len(dates)!=len(info["values"]) or dates!=sorted(set(dates)):raise ValueError("Invalid episode calendar")
        source=evidence["providers"];keys=keys_for(series,source)
        source_dates=set().union(*(source[k]["rows"].keys() for k in keys))
        expected=dict(zip(dates,info["values"]))
        for d in sorted(set(dates)|source_dates):
            record={"series":series,"date":d,"unit":UNIT[series],"calendar":METHOD[series],
                    "episode":str(expected[d]) if d in expected else None}
            available=[k for k in keys if d in source[k]["rows"]]
            closing=available[0] if available else None
            additional=[(p+"/"+d if p=="btc-snapshot" else p) for p in SECONDARY.get(series,[])]
            checks.append(record)
            if not closing:record.update(status="unavailable");continue
            original=source_value(source,closing,d)
            record.update(source=closing,observed=str(original),url=source[closing]["url"],
                          status=("missing in episode" if d not in expected else "match" if original==Decimal(str(expected[d])) else "different"),
                          corroboration={k:str(source_value(source,k,d)) for k in additional if k!=closing and k in source and d in source[k]["rows"]})
            if any(Decimal(x)!=original for x in record["corroboration"].values()): record["crossSourceDisagreement"]=True
    counts={state:sum(r["status"]==state for r in checks) for state in ("match","different","unavailable","missing in episode")}
    return {"receiptSha256":hashlib.sha256(receipt_bytes).hexdigest(),"episodeSha256":hashlib.sha256(episode_bytes).hexdigest(),
            "counts":counts,"providersUnavailable":[k for k,x in evidence["providers"].items() if x["status"]!="rows"],"checks":checks}


def discrepancies(summary):
    return [row for row in summary["checks"] if row["status"]!="match" or row.get("crossSourceDisagreement")]


def compare(episode, receipt, out):
    if out.exists():raise FileExistsError(f"La salida ya existe: {out}")
    summary=compare_rows(episode,receipt)
    names=["series","date","episode","observed","status","source","unit","calendar","url"]
    table=io.StringIO(newline="");writer=csv.DictWriter(table,names,extrasaction="ignore")
    writer.writeheader();writer.writerows(summary["checks"])
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as scratch:
        prepared=Path(scratch)/"result";prepared.mkdir()
        (prepared/"cierres.csv").write_bytes(table.getvalue().encode("utf-8"))
        (prepared/"comparacion.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        # Both complete files are ready before acquiring the destination. Each failed writer
        # removes only what it just created, without replacing an existing report.
        out.mkdir()
        published=[]
        try:
            for p in prepared.iterdir():
                final=out/p.name
                with p.open("rb") as incoming, final.open("xb") as output:
                    published.append(final);output.write(incoming.read())
        except BaseException:
            for final in published:final.unlink(missing_ok=True)
            if not any(out.iterdir()):out.rmdir()
            raise
    print(json.dumps(summary["counts"]));return int(bool(discrepancies(summary)))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest="cmd",required=True)
    cap=commands.add_parser("capture",help="Capturar un intervalo explícito.")
    cap.add_argument("start",type=date.fromisoformat);cap.add_argument("end",type=date.fromisoformat);cap.add_argument("out",type=Path)
    week=commands.add_parser("week-ending",help="Capturar desde siete días antes de la fecha de cierre elegida.")
    week.add_argument("end",type=date.fromisoformat);week.add_argument("out",type=Path)
    tables=commands.add_parser("add-public-tables",help="Incorporar las filas públicas de XAU/USD a un recibo nuevo.")
    tables.add_argument("prior",type=Path);tables.add_argument("english",type=Path)
    tables.add_argument("spanish",type=Path,nargs="?");tables.add_argument("out",type=Path)
    exp=commands.add_parser("export",help="Crear datos.json sin conexión desde el recibo.")
    exp.add_argument("receipt",type=Path);exp.add_argument("out",type=Path)
    exp.add_argument("--sessions",type=Path,help="JSON {serie:[fechas ISO observadas]} para calendarios revisados.")
    cmp=commands.add_parser("compare",help="Cotejar un episodio sin conexión en una carpeta nueva.")
    cmp.add_argument("episode",type=Path);cmp.add_argument("receipt",type=Path);cmp.add_argument("out",type=Path)
    args=parser.parse_args(argv)
    try:
        if args.cmd in ("capture","week-ending"):
            return collect(args.start if args.cmd=="capture" else args.end-timedelta(days=7),args.end,args.out)
        elif args.cmd=="add-public-tables":add_public_tables(args.prior,args.english,args.spanish,args.out)
        elif args.cmd=="export":extract_episode(args.receipt,args.out,args.sessions)
        else:return compare(args.episode,args.receipt,args.out)
    except (ValueError,OSError,KeyError,TypeError,ArithmeticError) as error:
        parser.exit(2,f"cierres: {error}\n")
    return 0


if __name__=="__main__":
    sys.exit(main())
