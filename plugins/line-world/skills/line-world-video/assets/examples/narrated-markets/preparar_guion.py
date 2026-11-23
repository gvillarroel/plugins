"""Escribe el guion hablado y su hoja visual a partir de cierres fechados."""
import argparse
from collections import Counter
from datetime import date
from decimal import Decimal,ROUND_HALF_UP,localcontext
from fractions import Fraction
import json
from pathlib import Path
import re
import tempfile

from generar import normalize,read,write
from validar import headline_start


PRICE_IDS=("sp500","nasdaq","oro","btc","tlt")
SMALL=("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete "
       "dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco veintiséis veintisiete "
       "veintiocho veintinueve").split()
TENS="treinta cuarenta cincuenta sesenta setenta ochenta noventa".split()
HUNDREDS="ciento doscientos trescientos cuatrocientos quinientos seiscientos setecientos ochocientos novecientos".split()
SCALES=(("millón","millones"),("billón","billones"),("trillón","trillones"),("cuatrillón","cuatrillones"))
MONTHS="enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def before_noun(words):
    if words.endswith("veintiuno"):return words[:-3]+"ún"
    if words.endswith("uno"):return words[:-3]+"un"
    return words


def integer(n):
    if n<0:return "menos "+integer(-n)
    if n<30:return SMALL[n]
    if n<100:
        tens,ones=divmod(n,10)
        return TENS[tens-3]+(" y "+SMALL[ones] if ones else "")
    if n==100:return "cien"
    if n<1000:
        hundreds,tail=divmod(n,100)
        return HUNDREDS[hundreds-1]+(" "+integer(tail) if tail else "")
    if n<10**6:
        groups,tail=divmod(n,1000)
        return ("mil" if groups==1 else before_noun(integer(groups))+" mil")+(" "+integer(tail) if tail else "")
    for index in reversed(range(len(SCALES))):
        count,tail=divmod(n,10**(6*(index+1)))
        if count:
            one,many=SCALES[index]
            return ("un "+one if count==1 else before_noun(integer(count))+" "+many)+(" "+integer(tail) if tail else "")


def rounded(value):
    # Both the numeric canvas and this draft use two decimal places for price readouts.
    with localcontext() as ctx:
        ctx.prec=max(40,len(str(abs(value.numerator)))+8)
        return (Decimal(value.numerator)/Decimal(value.denominator)).quantize(Decimal(".01"),rounding=ROUND_HALF_UP)


def words(value):
    value=Decimal(value)
    if value<0:return "menos "+words(-value)
    whole,_,fraction=format(value,"f").partition(".")
    fraction=fraction.rstrip("0")
    if not fraction:return integer(int(whole))
    head=fraction.lstrip("0")
    tail=["cero"]*(len(fraction)-len(head))+[integer(int(head))]
    return integer(int(whole))+" coma "+" ".join(tail)


def observed(series):
    return [Fraction(Decimal(str(v))) for v in (series["values"][0],series["values"][-1])]


def percent(series):
    first,last=observed(series)
    return 100*(last-first)/first


def sign(n):return (n>0)-(n<0)


def period(first,last):
    a,b=map(date.fromisoformat,(first,last))
    left=integer(a.day)
    if (a.year,a.month)!=(b.year,b.month):left+=" de "+MONTHS[a.month-1]
    if a.year!=b.year:left+=" de "+integer(a.year)
    return f"del {left} al {integer(b.day)} de {MONTHS[b.month-1]} de {integer(b.year)}"


def majority(changes):
    counts=Counter(sign(n) for n in changes.values())
    n=max(counts.values())
    leaders=[d for d in (-1,1,0) if counts[d]==n]
    if len(leaders)==1:
        verb={-1:"bajaron",1:"subieron",0:"cerraron sin cambio"}[leaders[0]]
        return ("las cinco referencias de precio" if n==5 else integer(n)+" de las cinco referencias de precio")+" "+verb
    groups={-1:"bajas",1:"alzas",0:"referencias sin cambio"}
    return "hubo un empate con "+" y ".join(integer(n)+" "+groups[d] for d in leaders)


def spoken_name(series):
    name=series.get("etiqueta") or series["nombre"]
    default={"S&P 500":"El S&P 500","Nasdaq Composite":"El Nasdaq Composite","Oro al contado":"El oro al contado",
            "Bitcoin":"Bitcóin","Bonos del Tesoro":"El fondo TLT","Bonos del Tesoro (TLT)":"El fondo TLT",
            "Tesoro a 10 años":"El rendimiento del Tesoro a diez años","Tesoro a diez años":"El rendimiento del Tesoro a diez años"}.get(name,name)
    return phrase_label(series.get("nombre_hablado") or default)


def phrase_label(raw):
    # A period followed by whitespace is a new Piper sentence. Keep names inside their own shot.
    clean=re.sub(r"\bEE\.\s*UU\.","Estados Unidos",raw,flags=re.I)
    clean=re.sub(r"[.!?]+(?=\s|$)","",clean)
    return " ".join(clean.split())


def movement(name,change):
    if not change:return name+" cerró sin cambio."
    verb="subió" if change>0 else "bajó"
    value=rounded(abs(change))
    if not value:return f"{name} {verb} menos de un cero coma cero uno por ciento."
    return f"{name} {verb} un {words(value)} por ciento."


def level(series):
    value=Decimal(str(series["values"][-1]))
    number=words(rounded(Fraction(value)))
    original=phrase_label(series.get("unidad_hablada") or series["unidad"])
    unit=original.replace("USD","dólares").replace("BTC","bitcóin").replace("EUR","euros")
    if original.startswith(("USD","EUR")) and value==1:
        unit=unit.replace("dólares","dólar",1).replace("euros","euro",1)
    if value>0 and rounded(Fraction(value))==0:
        return "menos de cero coma cero uno "+unit
    if value==int(value):
        preposition=" de " if value>=10**6 and int(value)%10**6==0 else " "
        return before_noun(number)+preposition+unit
    return number+" "+unit


def ranking_for(key,changes):
    amount=changes[key]
    if not amount:return None
    peers=[abs(v) for v in changes.values() if sign(v)==sign(amount)]
    rank=1+sum(v>abs(amount) for v in peers)
    ties=peers.count(abs(amount))
    ordinal={1:"mayor",2:"segunda mayor",3:"tercera mayor",4:"cuarta mayor",5:"quinta mayor"}[rank]
    noun="alza" if amount>0 else "caída"
    return rank,ties,f"la {ordinal} {noun} entre las cinco referencias de precio."


def rate_text(series):
    name=spoken_name(series)
    first,last=observed(series)
    if first==last:return f"{name} se mantuvo en {words(rounded(last))} por ciento."
    move=abs((last-first)*100)
    quantity=rounded(move)
    quantity_words=("menos de cero coma cero uno" if not quantity else
                    before_noun(words(quantity)) if quantity==int(quantity) else words(quantity))
    units="punto básico" if quantity==1 else "puntos básicos"
    if rounded(first)==rounded(last):
        return f"{name} {'subió' if last>first else 'bajó'} {quantity_words} {units}."
    return (f"{name} pasó de {words(rounded(first))} a {words(rounded(last))} por ciento, "
            f"una {'subida' if last>first else 'bajada'} de {quantity_words} {units}.")


def draft(data):
    data=normalize(data)
    series=data["series"]
    changes={k:percent(series[k]) for k in PRICE_IDS}
    spoken=[];visual=[]
    def add(scene,utterance,view,key,metric,start=0,end=1):
        if not spoken or spoken[-1]["id"]!=scene:spoken.append({"id":scene,"text":""})
        index=sum(row["scene"]==scene for row in visual)
        spoken[-1]["text"]+=(" " if index else "")+utterance
        visual.append({"scene":scene,"sentence":index,"view":view,"series":key,"metric":metric,
                       "from":start,"to":end,"idea":utterance})
    first, last = map(date.fromisoformat, (data["inicio"],data["fin"]))
    lower=period(headline_start(first,last).isoformat(),data["fin"])
    intro=("En los datos de prueba "+lower if data.get("sintetico") else lower.capitalize())
    add("intro",intro+", "+majority(changes)+".","breadth","conjunto","breadth")
    for key in ("sp500","nasdaq"):
        add("bolsa",movement(spoken_name(series[key]),changes[key]),"line",key,"change")
    for chapter,key in (("oro","oro"),("btc","btc")):
        summary=movement(spoken_name(series[key]),changes[key])
        ranking=ranking_for(key,changes)
        if key=="btc" and ranking and ranking[0]==1:
            _,ties,placement=ranking
            summary=summary[:-1]+(" y compartió " if ties>1 else " y registró ")+placement
        add(chapter,summary,"line" if key=="oro" else "ranking",key,"change",0,.35 if key=="oro" else 1)
        add(chapter,"El cierre fue de "+level(series[key])+".","line",key,"level",.35 if key=="oro" else 0,1)
        if key=="oro" and ranking:
            _,ties,placement=ranking
            add(chapter,("Compartió " if ties>1 else "Fue ")+placement,"ranking",key,"rank")
    tlt=spoken_name(series["tlt"])
    if tlt=="El fondo TLT" and not data.get("sintetico"):tlt+=" de bonos del Tesoro a más de veinte años"
    add("bonos",movement(tlt,changes["tlt"]),"line","tlt","change")
    a,b=observed(series["ust10"])
    mechanism={-1:"Para un bono de pagos fijos, un rendimiento exigido menor eleva el valor actual de esos pagos.",
                0:"Con los mismos pagos y la misma tasa de descuento, el valor actual se mantiene.",
                1:"Para un bono de pagos fijos, un rendimiento exigido mayor reduce el valor actual de esos pagos."}[sign(b-a)]
    add("bonos",mechanism,"coupon","ust10","mechanism")
    add("bonos",rate_text(series["ust10"]),"line","ust10","yield")
    visual[-1]['yieldUnit']='percentage-points'
    return {"preset":"neutral","seed":31,"caption_layout":"es-lectura",
            "pronunciations":{"S&P 500":"ese y pe quinientos","TLT":"te ele te"},"scenes":spoken},visual


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("--datos",type=Path,required=True)
    choice=ap.add_mutually_exclusive_group(required=True);choice.add_argument("--out",type=Path);choice.add_argument("--preview",action="store_true")
    args=ap.parse_args()
    try:
        audio,visual=draft(read(args.datos))
        if args.preview:
            print(json.dumps({"narracion":audio,"guionVisual":visual},ensure_ascii=False,indent=2));return
        dest=args.out.resolve()
        if dest.exists():raise ValueError("El destino ya existe. Escoge una carpeta nueva para conservar tus ediciones.")
        dest.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=dest.parent) as staging:
            folder=Path(staging)/"guion";folder.mkdir()
            write(folder/"narracion.json",audio);write(folder/"guion-visual.json",visual)
            folder.rename(dest)
        print(f"{len(audio['scenes'])} escenas y {len(visual)} frases en {dest}")
    except (OSError,ValueError,KeyError,TypeError) as exc:ap.exit(1,"preparar_guion: "+str(exc)+"\n")


if __name__=="__main__":main()
