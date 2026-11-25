"""Compose an editable scene from a new brief and its own observations, or route it to a specialist."""
import argparse
from datetime import date
import json
import math
import os
import sys
import tempfile
from pathlib import Path

from motion_recipe import check_props, require, words
from recommend_motion import (MISSING, match, normalize, number_value, profile_rows, read_records,
                              recommend, systems_study)
from relationship_layout import network, relation_of


ALIASES = {
    "source": ("source","from","origen","emisor","sender","parent","padre"),
    "target": ("target","to","destino","receptor","receiver","child","hijo"),
    "message": ("message","mensaje"), "order": ("order","orden","sequence","secuencia"),
    "group": ("group","grupo","familia","family"), "item": ("item","elemento","entidad","entity"),
    "before": ("before","antes"), "after": ("after","despues"),
    "step": ("step","paso","etapa","stage"), "category": ("category","categoria"),
    "value": ("value","valor"), "unit": ("unit","unidad"),
    "date": ("date","fecha"),
    "low": ("low","lower","min","minimo","inferior"), "high": ("high","upper","max","maximo","superior"),
    "x": ("x",), "y": ("y","altura","height"), "t": ("t","tiempo","time"),
    "timeUnit": ("timeunit","unidad temporal","unidad_tiempo","time_unit"),
}
# These anchors are also useful to a specialist when the native scene would be too crowded.
DIRECTIONS = {
    "fan-out": (18,"El origen conserva su posición.","Abre una conexión hacia cada destino y sigue la marca hasta su llegada."),
    "fan-in": (12,"El destino común queda visible.","Presenta cada origen y lleva la marca por su propia conexión al mismo destino."),
    "hierarchy": (11,"Las ramas conservan su identidad durante el ascenso de la raíz.","Abre un nivel a la vez y mantén cada conexión sujeta a los nodos."),
    "sequence": (13,"El orden espacial de los hitos permanece estable.","Avanza desde la etapa presente a la siguiente y conserva el recorrido completo."),
    "exchange": (9,"Los dos participantes conservan sus columnas.","Revela una fila por mensaje en el sentido y orden del registro."),
    "group-members": (12,"Cada grupo conserva un espacio identificable.","Dibuja los contenedores y deja que entren los miembros en su grupo."),
    "parallel-states": (13,"La identidad de cada fila permanece alineada en ambas columnas.","Abre las dos lecturas con encabezados constantes para cotejar sus diferencias."),
    "comparison": (None,"El cero, la unidad y la posición de cada categoría permanecen fijos.","Revela las categorías sobre la misma escala y conserva los valores finales."),
}
CONTENT_FIELDS = {
    "interval-refinement": {"unit", "intervals"},
    "trajectory-trace": {"unit", "timeUnit", "samples"},
    "bit-probe": {"labels","bits"}, "token-gate":{"labels","tokens","requests"},
    "radix-ladder":{"labels","base","value"}, "detail-callout":{"labels","parts","focusLabel"},
    "message-ladder":{"labels","exchanges"}, "import-footprint":{"labels","footprint"},
    "module-transfer":{"labels","highlightIndex","inputs","outputs"},
}
SPECIALTY = {
    "time-series-reveal":"line-world-d3", "stacked-category-comparison":"line-world-d3",
    "count-threshold":"line-world-d3", "progressive-table":"line-world-d3",
    "recursive-spatial-partition":"line-world-d3", "context-detail":"line-world-d3",
    "item-reassignment":"line-world-motion-direction", "lane-handoff":"line-world-motion-direction",
    "repeated-event":"line-world-motion-direction", "selected-route":"line-world-mermaid",
    "merge-lineage":"line-world-mermaid", "broadcast-bus":"line-world-mermaid",
}


def label(value):
    require(isinstance(value,str) and value.strip() and value.strip().casefold() not in MISSING,
            "Cada entidad o mensaje necesita una etiqueta de la fuente.")
    return value.strip()


def columns_for(rows, supplied):
    require(isinstance(supplied,dict) and set(supplied)<=set(ALIASES), "Mapeo fields desconocido.")
    keys=list(dict.fromkeys(k for row in rows for k in row))
    result={}
    for role,aliases in ALIASES.items():
        if role in supplied:
            column=supplied[role]
            require(isinstance(column,str) and column in keys, f"Columna inexistente para {role}: {column}")
            result[role]=column
        else:
            candidates=[k for k in keys if normalize(k).strip() in aliases]
            if len(candidates)==1: result[role]=candidates[0]
    return result


def provenance(index):
    video=next(v for v in systems_study()["videos"] if v["index"]==index)
    return dict(video_id=video["video_id"],url=video["url"],source_s=video["source_s"],anchor=video["anchor"],
                motion=" ".join(video["observations"]),transfer=video["name"],limitation=video["adaptation"])


def ordered(rows, fields):
    column=fields.get("order")
    require(column is not None,"La secuencia necesita un orden explícito.")
    keys=[number_value(row.get(column)) for row in rows]
    require(None not in keys and len(set(keys))==len(rows),"El orden necesita números finitos y sin empates.")
    return [row for _,row in sorted(zip(keys,rows), key=lambda pair:pair[0])]


def compare(rows, fields, req):
    labels=[label(row.get(fields["category"])) for row in rows]
    values=[number_value(row.get(fields["value"])) for row in rows]
    require(len(set(labels))==len(labels),"Cada categoría necesita una sola observación comparable.")
    require(None not in values, "Una medida pendiente requiere un gráfico que conserve el hueco.")
    require(2<=len(values)<=8, "Para esta cantidad de categorías se necesita otra disposición.")
    units={label(r.get(fields["unit"])) for r in rows} if "unit" in fields else set()
    if req.get("unit"): units.add(label(req["unit"]))
    require(len(units)==1,"Indica una unidad común para las medidas.")
    props=dict(labels=labels,values=values,title=req.get("title") or fields["value"],unit=units.pop(),
               duration=req.get("duration",1.5))
    if "focus" in req:
        require(req["focus"] in labels,"La categoría destacada debe existir en la tabla.")
        props.update(highlightIndex=labels.index(req["focus"]),focusHold=1.6)
    return props


def dated_chart(rows, fields, req):
    profile=profile_rows(rows)
    for role,key in (("date","dates"),("value","measures"),("unit","units")):
        if role not in fields and len(profile[key])==1: fields[role]=profile[key][0]
    require({"date","value"}<=fields.keys(), "Indica una fecha y la medida que debe trazarse.")
    units={label(r.get(fields["unit"])) for r in rows} if "unit" in fields else set()
    if "unit" in req: units.add(label(req["unit"]))
    require(len(units)==1, "La serie necesita una unidad común.")
    unit=units.pop()
    title=req.get("title",fields["value"])
    require(len(unit)<=48 and len(title)<=84,"El productor necesita una unidad o un título más corto.")
    require(2<=len(rows)<=2000, "La serie necesita entre dos y dos mil observaciones.")
    duration=req.get("duration",8)
    require(duration>=2,"La serie necesita al menos dos segundos.")
    points=[]
    for r in rows:
        day=r.get(fields["date"])
        require(isinstance(day,str) and len(day)==10 and date.fromisoformat(day).isoformat()==day,
                "Para el eje diario se necesitan fechas ISO completas.")
        require(fields["value"] in r, "Falta la columna de medida en una observación.")
        raw=r[fields["value"]]
        missing=raw is None or isinstance(raw,str) and raw.strip().casefold() in MISSING
        v=None if missing else number_value(raw)
        require(missing or (v is not None and abs(v)<=1e9), "La medida requiere un valor numérico del rango del productor, o un dato ausente.")
        points.append(dict(date=day,value=v))
    require(len({r["date"] for r in points})==len(points),"Hay varias medidas en la misma fecha. Identifica primero la serie.")
    return dict(kind="time-series",id="serie",title=title,unit=unit,locale="es-ES",duration=duration,revealObservations=True,
                observations=sorted(points,key=lambda r:r["date"]))


def adapt(req):
    from study_direction import find_direction
    from study_layouts import grouped_rows, parallel_rows
    require(isinstance(req,dict) and set(req)<={"brief","rows","fields","data","content","intent","concepts","unit","focus","title","duration","narration"},
            "La solicitud contiene campos desconocidos.")
    brief=req.get("brief","")
    require(isinstance(brief,str),"brief debe ser texto.")
    require("intent" not in req or isinstance(req["intent"],str),"intent debe ser un identificador de texto.")
    rows=req.get("rows",[])
    require(isinstance(rows,list) and all(isinstance(r,dict) and all(
        isinstance(k,str) and k.strip() and not isinstance(v,(dict,list)) for k,v in r.items()) for r in rows),
        "rows requiere registros con campos escalares.")
    inputs=sum(k in req for k in ("rows","content","concepts"))
    require(inputs<=1,"Usa una sola fuente entre rows, data, concepts y content.")
    duration=req.get("duration",6)
    require(type(duration) in (int,float) and math.isfinite(duration) and duration>0,"duration debe ser un tiempo positivo.")
    for k in ("title","unit","focus"):
        if k in req: label(req[k])
    fields=columns_for(rows,req.get("fields",{}))
    choices=recommend(brief, rows or None, req.get("intent"))
    choice=choices["recommendation"] or {}
    question=choices["question"]
    kind=choice.get("id")
    relation=kind
    producer=choice.get("producer","reference-motion")
    status="needs-input"
    props=artifact=None
    if choice.get("kind")=="static":
        status="static"
    elif "content" in req:
        content=req["content"]
        require(isinstance(content,dict),"content debe ser un objeto.")
        if kind in CONTENT_FIELDS and CONTENT_FIELDS[kind]<=content.keys():
            props={**content,"duration":duration}
            if kind in ("interval-refinement","trajectory-trace") and req.get("title"):
                props.setdefault("title",req["title"])
            check_props(kind,props,set())
            artifact=kind
        else:
            question=choice.get("next_step") or question or "Indica la relación y los parámetros del mecanismo."
    elif "concepts" in req:
        # The writer supplies a real, explicitly ordered list extracted from the brief.
        concepts=req["concepts"]
        require(isinstance(concepts,list) and len(concepts)>=2,"concepts requiere al menos dos etapas en orden.")
        names=[label(c) for c in concepts]
        require(len(set(names))==len(names),"Para ciclos o etapas repetidas usa conexiones con identidad explícita.")
        if choice.get("fit") == "study-direction":
            status, question = "specialist", choice["next_step"]
        elif kind in ("trajectory-trace","interval-refinement"):
            question = "La escena necesita observaciones numéricas con sus unidades."
        else:
            relation="sequence"
            try:
                props=network(list(zip(names,names[1:])),relation,duration)
                artifact="staged-network"
            except ValueError as e:
                status,producer,question="specialist","line-world-mermaid",str(e)
    elif rows:
        # The question takes precedence over a coincidental numerical or graph structure.
        qualitative_pair={"before","after","item"}<=fields.keys() and all(
            isinstance(r.get(fields[role]),str) and number_value(r.get(fields[role])) is None
            for r in rows for role in ("before","after"))
        learned=choices.get("study_directions",[])
        specific=learned[0].get("relation") if learned else None
        if kind == "trajectory-trace":
            if {"x","y","t","timeUnit"} <= fields.keys():
                time_units = {label(r.get(fields["timeUnit"])) for r in rows}
                units = {label(r.get(fields["unit"])) for r in rows} if "unit" in fields else set()
                if req.get("unit"):
                    units.add(label(req["unit"]))
                require(len(units) == 1 and len(time_units) == 1, "Utiliza unidades espaciales y temporales comunes.")
                samples = [{k:number_value(r.get(fields[k])) for k in ("x","y","t")} for r in rows]
                require(all(s["t"] is not None for s in samples), "Cada muestra necesita un tiempo válido.")
                props = dict(title=req.get("title", ""), unit=units.pop(), timeUnit=time_units.pop(),
                             duration=duration, samples=sorted(samples,key=lambda s:s["t"]))
                artifact = kind
            else:
                question = "Indica x, y, tiempo, unidad espacial y unidad temporal para cada muestra."
        elif kind == "interval-refinement":
            needed = {"step", "order", "low", "high"}
            if needed <= fields.keys():
                ordered_steps = ordered(rows, fields)
                units = {label(r.get(fields["unit"])) for r in rows} if "unit" in fields else set()
                if req.get("unit"):
                    units.add(label(req["unit"]))
                require(len(units) == 1, "Indica una unidad común para todos los extremos.")
                props = dict(title=req.get("title", ""), unit=units.pop(), duration=duration, intervals=[
                    dict(label=label(r.get(fields["step"])), low=number_value(r.get(fields["low"])),
                         high=number_value(r.get(fields["high"]))) for r in ordered_steps])
                artifact = kind
            else:
                question = "Indica el orden, la etapa, el límite inferior, el superior y su unidad común."
        elif not kind and {"date","value"}<=fields.keys() and choices["decision"]!="ambiguous":
            status,producer,relation="specialist","line-world-d3","time-series-reveal"
        elif specific in {"stacked-category-comparison","time-series-reveal","count-threshold","progressive-table"} and not req.get("intent"):
            status,producer,relation="specialist","line-world-d3",specific
        elif {"source","target","value"}<=fields.keys() and match(
                r"cantidad\w*|cuanto\w*|volumen\w*|caudal\w*|weights?|amounts?|volumes?|how much",normalize(brief)):
            status,producer,relation="specialist","line-world-d3","weighted-flow"
            question="Representa la medida y su unidad sobre cada enlace con una escala común."
        elif choice.get("kind")=="specialist" and kind!="node-link" and not (kind=="paired-change" and qualitative_pair):
            status="specialist"
        elif choices["decision"]=="ambiguous" and not (qualitative_pair and
                {v["intent"] for v in choices["alternatives"]} <= {"lookup","paired-change"}):
            pass
        else:
            roles=set(fields)
            if {"source","target"}<=roles and kind!="data-chart":
                try:
                    pairs=[(label(r.get(fields["source"])),label(r.get(fields["target"]))) for r in rows]
                    endpoints=list(dict.fromkeys(v for pair in pairs for v in pair))
                    if "message" in fields and len(endpoints)==2 and all(a!=b for a,b in pairs):
                        relation="exchange"
                        in_order=ordered(rows,fields)
                        require(len(rows)<=6,"Más de seis mensajes requieren repartir el intercambio en varios planos.")
                        people=list(dict.fromkeys(label(r[fields[key]]) for r in in_order for key in ("source","target")))
                        props=dict(labels=people,duration=duration,exchanges=[
                            {"from":people.index(label(r[fields["source"]])),"label":label(r.get(fields["message"]))}
                            for r in in_order])
                        artifact="message-ladder"
                    else:
                        relation=relation_of(pairs)
                        require(relation is not None,"La red requiere un trazado que conserve sus ciclos, repeticiones o componentes.")
                        require("message" not in roles,"Conserva el mensaje de cada enlace en una vista de flujo anotada.")
                        if "order" in roles:
                            in_order=ordered(rows,fields)
                            pairs=[(label(r[fields["source"]]),label(r[fields["target"]])) for r in in_order]
                        props=network(pairs,relation,duration)
                        artifact="staged-network"
                except ValueError as e:
                    status,producer,question="specialist","line-world-mermaid",str(e)
            elif {"item","before","after"}<=roles or {"group","item"}<=roles:
                paired={"before","after"}<=roles
                relation="parallel-states" if paired else "group-members"
                try:
                    require(not paired or qualitative_pair,"Para extremos medidos, conserva ambas cantidades en una escala común.")
                    props=(parallel_rows if paired else grouped_rows)(rows,fields,duration)
                    artifact="staged-network"
                except ValueError as e:
                    status,producer,question="specialist","line-world-d3",str(e)
            elif "step" in fields and "order" in fields:
                ordered_names=[label(r.get(fields["step"])) for r in ordered(rows,fields)]
                return adapt({**{k:v for k,v in req.items() if k not in {"rows","data","fields"}},
                              "concepts":ordered_names})
            elif kind=="data-chart" or ({"category","value"}<=roles and not kind and choices["decision"]!="ambiguous"):
                profile=profile_rows(rows)
                for role,key in (("value","measures"),("category","categories"),("unit","units")):
                    if role not in fields and len(profile[key])==1: fields[role]=profile[key][0]
                relation="comparison"
                if {"category","value"}<=fields.keys():
                    try:
                        props=compare(rows,fields,req)
                        artifact="data-chart"
                    except ValueError as e:
                        status,producer,question="specialist","line-world-d3",str(e)
                else:
                    question="Indica las columnas que contienen la categoría y su medida."
    elif choice.get("kind")=="specialist":
        status="specialist"
    if artifact:
        status,producer,question="recipe","reference-motion",None
        check_props(artifact,props,set())
    if relation=="time-series":
        relation="time-series-reveal"
    references=find_direction(brief, relation)
    anchor=choice.get("anchor","")
    motion=choice.get("motion","")
    if relation in DIRECTIONS:
        index,anchor,motion=DIRECTIONS[relation]
        if not references and index: references=[provenance(index)]
    if not references and choice.get("source","").startswith("https://"):
        references=[{"url":choice["source"],"anchor":anchor,"motion":motion}]
    if references and not artifact and status!="static":
        lesson=references[0]
        # A retrieved passage gives a specialist a concrete composition even when a
        # native artifact cannot express the question or needs a different shape of data.
        if (not choice or choice.get("kind")=="specialist") and choices["decision"]!="ambiguous":
            if status=="needs-input" and lesson.get("transfer"):
                status,producer="specialist",SPECIALTY.get(lesson.get("relation"),"line-world-hyperframes")
            if status=="specialist" and lesson.get("transfer"):
                relation=relation or lesson.get("relation")
                anchor=lesson.get("anchor",anchor)
                motion=lesson["transfer"]
    if status=="static":
        motion="Mantén visibles las observaciones para su lectura."
    if references and relation not in DIRECTIONS and status!="static":
        anchor=anchor or references[0].get("anchor","")
        motion=motion or references[0].get("transfer","")
    recipe=None
    if artifact:
        hold=max(2.5,math.ceil(words(props)/3*10)/10)
        recipe={"version":1,"width":1280,"height":720,"fps":24,"scenes":[
            {"id":"escena","artifact":artifact,"props":props,"hold":hold}]}
    report=dict(status=status,producer=producer,relation=relation,artifact=artifact,
                reference=references[0] if references else None, references=references,
                direction={"anchor":anchor,"motion":motion,"hold":recipe["scenes"][0]["hold"] if recipe else None},
                fields=fields,question=question,alternatives=choices["alternatives"])
    from analyze_pose_mentions import timing_reference
    measured=timing_reference(report["reference"])
    if measured: report["direction"]["voice_pose_reference"]=measured
    if not recipe: report["input"]=req
    if status=="specialist" and producer=="line-world-d3" and relation=="time-series-reveal" and rows:
        try:
            report["d3_chart"]=dated_chart(rows,fields,req)
            report["question"]=None
        except ValueError as exc:
            report["question"]=str(exc)
    if "narration" in req:
        from narration_poses import bind, cue_list
        from motion_recipe import DIAGRAM_KINDS
        narration=req["narration"]
        if recipe and artifact in DIAGRAM_KINDS:
            report["narration"]=bind(recipe["scenes"][0],narration,recipe["fps"])
        else:
            duration,cues=cue_list(narration)
            report["narration"]={"status":"handoff","duration_s":duration,"cues":cues,
                                 "note":"El productor de esta representación recibe marcas para dirigir sus propias poses."}
            if recipe:
                report.update(status="specialist",producer="line-world-d3" if artifact=="data-chart" else "line-world-hyperframes",
                              input=req)
                recipe=None
    return recipe,report


def add_arguments(parser):
    parser.add_argument("request",type=Path)
    parser.add_argument("--out",required=True,type=Path)
    parser.add_argument("--report",required=True,type=Path)


def run(args):
    req=json.loads(args.request.read_text(encoding="utf-8-sig"))
    require(isinstance(req,dict),"La solicitud debe ser un objeto JSON.")
    inputs={args.request.resolve()}
    if "data" in req:
        require("rows" not in req and isinstance(req["data"],str),"Indica una ruta de tabla o rows.")
        data=args.request.parent/req.pop("data")
        inputs.add(data.resolve())
        req["rows"]=read_records(data)
    destinations={args.out.resolve(),args.report.resolve()}
    require(len(destinations)==2 and not inputs & destinations,"Las entradas y salidas requieren rutas distintas.")
    require(not args.out.exists() and not args.report.exists(),"Elige rutas nuevas para la receta y el informe.")
    recipe,report=adapt(req)
    documents=[(args.report,report)]+([(args.out,recipe)] if recipe else [])
    staged=[]
    published=[]
    try:
        for path,doc in documents:
            path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",dir=path.parent,delete=False) as f:
                staged.append((Path(f.name),path))
                f.write(json.dumps(doc,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
        # The temporary files live on the destination volumes. A hard link atomically
        # publishes a complete file only if its destination is still free.
        for tmp,path in staged:
            os.link(tmp,path)
            published.append((tmp,path))
    except OSError:
        for tmp,path in reversed(published):
            if path.exists() and path.samefile(tmp): path.unlink()
        raise
    finally:
        for tmp,_ in staged: tmp.unlink(missing_ok=True)
    print(report["status"],"·",report["producer"],"·",args.out if recipe else args.report)


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    add_arguments(cli)
    try: run(cli.parse_args())
    except (ValueError,OSError) as exc: cli.exit(2,str(exc)+"\n")
