"""Validate editorial inputs and compile a frame-aligned, forward-only scene clock."""
import json
import math
import re
from pathlib import Path

from systems_recipe import validate_system
from narration_poses import validate_clock


DIAGRAM_LABEL_COUNTS = {
    "field-packing": 4, "layer-preview": 4, "isometric-layers": 5, "module-transfer": 5,
    "vertex-remap": 2, "command-lanes": 4, "shared-host": 3, "split-clock": 2,
    "pass-strip": 4, "import-footprint": 3,
    "ring-handoff": 5, "bit-probe": 3, "message-ladder": 2, "detail-callout": 4, "radix-ladder": 3, "token-gate": 4, "resolution-fan": 8, "queue-router": 5,
}


DIAGRAM_KINDS = set(DIAGRAM_LABEL_COUNTS) | {"staged-network", "interval-refinement", "trajectory-trace"}


FIELDS = {
    **dict.fromkeys(DIAGRAM_LABEL_COUNTS, "labels duration"),
    "ring-handoff": "labels duration keyLabel",
    "bit-probe": "labels duration bits",
    "message-ladder": "labels duration exchanges",
    "detail-callout": "labels duration parts focusLabel",
    "radix-ladder": "labels duration value base",
    "token-gate": "labels duration tokens requests",
    "queue-router": "labels duration inputLabel criteria",
    "staged-network": "duration nodes edges",
    "interval-refinement": "duration title unit intervals",
    "trajectory-trace": "duration title unit timeUnit samples",
    "module-transfer": "labels duration highlightIndex inputs outputs",
    "import-footprint": "labels duration footprint",
    "speaker-id": "title detail side background", "question-card": "title background", "caption-overlay": "title media position",
    "editorial-split": "title detail media share", "slide-pip": "slide media box presenter faceBox",
    "insight-band": "title detail kicker media side", "dashboard-stack": "cards beat",
    "icon-card": "points title side", "disc-endcard": "title detail mark hold moveDuration enterDuration finalY detailScale",
    "chart-focus": "box background padding", "corner-card": "title", "orbital-caption": "title x y delay background anchor",
    "numbered-step": "title number", "keypoint-list": "items starts beat x y spacing",
    "chart-ring": "value duration label fractional", "guest-grid": "guests", "type-title": "title detail",
    "cta-card": "title detail cta", "brand-slate": "title mark",
    "metric-callout": "value label detail media", "concept-diagram": "title nodes",
    "circle-window": "title media side", "data-chart": "title detail values labels unit highlightIndex duration focusHold",
}


def require(value, message):
    if not value:
        raise ValueError(message)


def number(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum


def words(value):
    if isinstance(value, dict):
        visible={"title","detail","kicker","value","values","label","labels","cta","unit","items","text","number","name","presenter","nodes","cards","guests","inputs","outputs","edges","keyLabel","inputLabel","focusLabel","exchanges","parts","criteria","intervals"}
        return sum(words(v) for k,v in value.items() if k in visible)
    if isinstance(value, list):
        return sum(words(v) for v in value)
    if isinstance(value, str):
        return len(value.split())
    return int(type(value) in (float,int))


def check_props(kind, p, assets):
    require(isinstance(p,dict), "props debe ser un objeto JSON")
    allowed=set(FIELDS[kind].split())
    if kind in DIAGRAM_KINDS: allowed.add("poseClock")
    if kind=="staged-network": allowed.add("poseFocus")
    if kind in ("staged-network","message-ladder"): allowed.add("poseLabels")
    require(set(p) <= allowed, f"{kind}: propiedad desconocida {set(p)-allowed}")
    string_fields = {"title","detail","label","kicker","unit","cta","presenter"}
    for k in string_fields & p.keys():
        require(isinstance(p[k], str), f"{kind}.{k} debe ser texto")
    def media(v):
        require(isinstance(v,str) and v in assets, f"{kind}: medio sin definir {v!r}")
    for k in {"mark","slide","media","background"} & p.keys():
        media(p[k])
    if "position" in p:
        require(p["position"] in ("top","center","bottom"),"caption-overlay.position debe ser top, center o bottom")
    if "padding" in p:
        require(number(p["padding"]) and p["padding"]<=.15,"chart-focus.padding debe estar entre 0 y 0,15")
    for k in {"x","y","share","spacing","finalY"} & p.keys():
        require(number(p[k]) and p[k]<=1, f"{kind}.{k} fuera del encuadre")
    for k in {"beat","hold","delay","duration","moveDuration","enterDuration"} & p.keys():
        require(number(p[k]) and (k in {"hold","delay"} or p[k]>0), f"{kind}.{k} debe ser un tiempo válido")
    if "side" in p:
        sides = {"insight-band":{"top","bottom"}, "circle-window":{"left","right","center"}}
        require(isinstance(p["side"],str) and p["side"] in sides.get(kind,{"left","right"}),f"{kind}.side no válido")
    if kind=="disc-endcard":
        require(p.get("hold",2.4)>=1.5 and p.get("moveDuration",1.4)>=1,"El cierre necesita 1,5 s centrado y 1 s para desplazarse")
        if "detailScale" in p:
            require(number(p["detailScale"], .03) and p["detailScale"] <= .12,
                    "detailScale debe estar entre 0,03 y 0,12 de la altura del cuadro")
    if kind in {"data-chart","chart-ring"}:
        require(p.get("duration",1.8)>=.8,"Reserva al menos 0,8 s para la aparición del dato")
    if kind == "chart-ring":
        require(number(p.get("value")) and p["value"]<=100, "chart-ring.value debe estar entre 0 y 100")
        require(p.get("fractional",True) is True, "El anillo de datos debe corresponder al porcentaje")
    if kind == "metric-callout":
        require(isinstance(p.get("value"),str) and p["value"].strip() or number(p.get("value"),-math.inf), "Falta el valor de la métrica")
    if "number" in p:
        require(number(p["number"]) or isinstance(p["number"],str) and p["number"].strip(), "Número de paso inválido")
    if "points" in p:
        require(isinstance(p["points"],list) and len(p["points"])>=2 and all(isinstance(v,list) and len(v)==2 and all(number(n) and n<=1 for n in v) for v in p["points"]), "points necesita pares entre 0 y 1")
    def normalized_box(value, name):
        require(isinstance(value,list) and len(value)==4 and all(number(v) for v in value)
                and value[2]>0 and value[3]>0 and value[0]+value[2]<=1 and value[1]+value[3]<=1,
                f"{name} requiere [x,y,ancho,alto] de 0 a 1 dentro de la imagen")
    if "box" in p:
        normalized_box(p["box"],"box")
    if "faceBox" in p:
        normalized_box(p["faceBox"],"faceBox")
    if "presenter" in p:
        require(p["presenter"].strip(),"presenter necesita un nombre visible")
    if "anchor" in p:
        anchor=p["anchor"]
        require(isinstance(anchor,list) and len(anchor)==2 and all(number(v) and v<=1 for v in anchor),
                "orbital-caption.anchor requiere [x,y] de 0 a 1 dentro del cuadro")
    def values(v):
        return isinstance(v,list) and len(v)>0 and all(number(n,-math.inf) for n in v)
    def series(v):
        ns=v.get("values")
        require(values(ns), "Cada serie necesita valores numéricos finitos")
        if "labels" in v:
            require(isinstance(v["labels"],list) and len(v["labels"])==len(ns) and all(isinstance(s,str) and s.strip() for s in v["labels"]), "Cada barra necesita su etiqueta")
        if "highlightIndex" in v:
            ix=v["highlightIndex"]
            require(type(ix) is int and 0<=ix<len(ns), "El índice de énfasis debe señalar una barra existente")
    if kind == "data-chart":
        require("labels" in p, "Cada barra necesita una etiqueta")
        series(p)
        if "focusHold" in p:
            require("highlightIndex" in p and number(p["focusHold"], 1.5),
                    "focusHold requiere highlightIndex y al menos 1,5 s para leer el dato destacado")
    if kind == "concept-diagram":
        require(isinstance(p.get("nodes"),list) and len(p["nodes"])>0 and all(isinstance(n,str) and n.strip() for n in p["nodes"]), "Cada nodo debe tener nombre")
    if kind in DIAGRAM_LABEL_COUNTS:
        labels = p.get("labels")
        count = DIAGRAM_LABEL_COUNTS[kind]
        require(isinstance(labels, list) and len(labels) == count
                and all(isinstance(label, str) and label.strip() for label in labels),
                f"{kind}: se requieren {count} etiquetas de texto en labels")
    validate_system(kind, p)
    validate_clock(p, kind)
    if kind == "trajectory-trace":
        samples = p.get("samples")
        require(isinstance(samples, list) and 2 <= len(samples) <= 400,
                "La trayectoria necesita entre 2 y 400 muestras.")
        require(all(isinstance(p.get(k), str) and p[k].strip() for k in ("unit", "timeUnit")),
                "Indica una unidad espacial y una unidad temporal.")
        for sample in samples:
            require(isinstance(sample, dict) and set(sample) == {"t", "x", "y"} and
                    all(number(v, -math.inf) and abs(v) <= 1e12 for v in sample.values()),
                    "Cada muestra necesita t, x e y finitos dentro de ±10¹².")
        require(all(a["t"] < b["t"] for a, b in zip(samples, samples[1:])),
                "Cada muestra necesita un instante distinto en orden creciente.")
    if kind == "interval-refinement":
        intervals = p.get("intervals")
        require(isinstance(intervals, list) and 2 <= len(intervals) <= 7,
                "Se necesitan entre dos y siete intervalos ordenados.")
        require(bool(p.get("unit", "").strip()), "Indica la unidad común de los intervalos.")
        previous = direction = None
        for interval in intervals:
            require(isinstance(interval, dict) and set(interval) == {"label", "low", "high"},
                    "Cada intervalo necesita label, low y high.")
            low, high = interval["low"], interval["high"]
            require(isinstance(interval["label"], str) and interval["label"].strip(),
                    "Cada intervalo necesita un nombre.")
            require(number(low, -math.inf) and number(high, -math.inf) and low < high and math.isfinite(high-low),
                    "Los extremos del intervalo deben ser finitos y crecientes.")
            if previous:
                a, b = previous
                narrower = a <= low and high <= b
                wider = low <= a and b <= high
                require(narrower != wider, "Cada intervalo debe contener al anterior o estar contenido en él y tener otra amplitud.")
                step = "in" if narrower else "out"
                require(direction in (None, step), "Mantén el sentido de la ampliación dentro del mismo plano.")
                direction = step
            previous = low, high
    if kind == "module-transfer":
        index = p.get("highlightIndex", 1)
        require(type(index) is int and 0 <= index < len(p["labels"]),
                "module-transfer.highlightIndex debe indicar una fila del inventario")
        for field in ("inputs", "outputs"):
            if field in p:
                ports = p[field]
                require(isinstance(ports, list) and 1 <= len(ports) <= 3
                        and all(isinstance(port, str) and port.strip() for port in ports),
                        f"module-transfer.{field} requiere entre uno y tres nombres de puerto")
    if kind == "import-footprint" and "footprint" in p:
        footprint = p["footprint"]
        require(isinstance(footprint, dict) and set(footprint) == {"total", "unit", "groups"},
                "import-footprint.footprint requiere total, unit y groups")
        total, unit, groups = (footprint[key] for key in ("total", "unit", "groups"))
        require(type(total) is int and 1 <= total <= 240, "footprint.total debe ser un entero entre 1 y 240")
        require(isinstance(unit, str) and bool(unit.strip()) and len(unit) <= 12,
                "footprint.unit requiere entre uno y doce caracteres")
        require(isinstance(groups, list) and len(groups) == 3, "footprint.groups requiere tres listas")
        for cells in groups:
            require(isinstance(cells, list) and all(type(i) is int and 0 <= i < total for i in cells)
                    and len(set(cells)) == len(cells),
                    "Cada lista de footprint.groups debe contener índices de celda válidos y únicos")
    if kind == "keypoint-list":
        items=p.get("items")
        require(isinstance(items,list) and len(items)>0 and all(isinstance(s,str) and s.strip() or isinstance(s,dict) and set(s)<={"text","accent"} and isinstance(s.get("text"),str) and s["text"].strip() for s in items), "Lista sin viñetas legibles")
        if "starts" in p:
            v=p["starts"]
            require(isinstance(v,list) and len(v)==len(items) and all(number(n) for n in v) and all(b-a>=1 for a,b in zip(v,v[1:])), "Deja al menos 1 s entre entradas de viñetas")
        else:
            require(p.get("beat",1.5)>=1, "Deja al menos 1 s entre entradas de viñetas")
    if kind == "dashboard-stack":
        cards=p.get("cards")
        require(isinstance(cards,list) and 1<=len(cards)<=4, "El tablero admite entre una y cuatro tarjetas")
        require(p.get("beat",2.8)>=2, "Deja al menos 2 s por tarjeta del tablero")
        for card in cards:
            require(isinstance(card,dict) and set(card)<={"title","media","values","labels","highlightIndex","unit"} and isinstance(card.get("title"),str) and card["title"].strip(),"Tarjeta sin título o con campos desconocidos")
            if "media" in card: media(card["media"])
            else: series(card)
    if kind == "guest-grid":
        guests=p.get("guests")
        require(isinstance(guests,list) and 1<=len(guests)<=4, "El mosaico admite de uno a cuatro participantes")
        for guest in guests:
            require(isinstance(guest,dict) and set(guest)<={"name","media","faceBox"} and isinstance(guest.get("name"),str) and guest["name"].strip(),"Participante sin nombre")
            if "faceBox" in guest:
                normalized_box(guest["faceBox"],"faceBox")
            media(guest.get("media"))
    if kind in {"type-title","question-card","caption-overlay","speaker-id","numbered-step","corner-card","icon-card","orbital-caption","editorial-split"}:
        require(p.get("title","").strip(), f"{kind} necesita texto visible")


BAR_GROUP_PAUSE = .25


def reveal_time(kind, p):
    if kind in DIAGRAM_KINDS:
        return p.get("duration", 5)
    if kind=="keypoint-list":
        return (max(p["starts"]) if "starts" in p else (len(p["items"])-1)*p.get("beat",1.5))+.7
    if kind=="dashboard-stack":
        beat=p.get("beat",2.8)
        total=0
        for card in p["cards"]:
            groups=1 if "media" in card else max(1,math.ceil(len(card["values"])/3))
            group_seconds=max(.8 if groups>1 else 0,min(.9,beat*.28))
            total+=max(beat,groups*group_seconds+(groups-1)*BAR_GROUP_PAUSE+.4)
        return total+.7
    if kind=="disc-endcard": return p.get("hold",2.6)+p.get("moveDuration",2.2)+p.get("enterDuration",.75)+1
    if kind=="orbital-caption":
        return max(.35,p.get("delay",2))+.60 if "anchor" in p else p.get("delay",2)+1.1
    if kind=="slide-pip" and p.get("presenter"): return 2.60
    if kind=="chart-ring": return p.get("duration",1.8)+.2
    if kind=="concept-diagram": return .28+.70*len(p["nodes"])+.12
    if kind=="data-chart":
        focus_hold=p.get("focusHold",0)
        advancing=len(p["values"])-int(focus_hold>0)
        groups=max(1,math.ceil(advancing/3))
        return p.get("duration",1.25)*groups+(groups-1)*BAR_GROUP_PAUSE+focus_hold+.6
    return 2.1


HANDOFFS = {
    "section": ("push-down", "Abrir una sección nueva."),
    "comparison": ("push-left", "Pasar al segundo término de una comparación."),
    "detail": ("iris-fill", "Acercar la atención al detalle anunciado."),
}


def transition_policy(spec):
    supplied = spec.get("transition_policy", {})
    require(isinstance(supplied, dict) and set(supplied) <= {"mode", "joins_per_effect", "min_gap_seconds"},
            "transition_policy contiene campos desconocidos")
    policy = {"mode": "occasional", "joins_per_effect": 4, "min_gap_seconds": 12, **supplied}
    require(policy["mode"] in ("occasional", "cuts-only"), "Modo de transición desconocido")
    require(type(policy["joins_per_effect"]) is int and policy["joins_per_effect"] >= 3,
            "joins_per_effect debe ser un entero de al menos 3")
    require(number(policy["min_gap_seconds"]), "min_gap_seconds debe ser un número no negativo")
    return policy


def same_highlight(metric, chart):
    """Only infer a comparison when both the measure and the selected value match."""
    value = str(metric.get("value", "")).strip().replace(",", ".")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", value):
        return False
    label = " ".join(metric.get("label", "").casefold().split())
    title = " ".join(chart.get("title", "").casefold().split())
    index = chart.get("highlightIndex")
    return bool(label and label == title and index is not None and float(value) == chart["values"][index])


def preserves_data_anchor(previous, current):
    if {previous["artifact"],current["artifact"]} != {"metric-callout","data-chart"}:
        return False
    metric, chart = (previous, current) if previous["artifact"] == "metric-callout" else (current, previous)
    return same_highlight(metric["props"], chart["props"])


def handoff_candidate(previous, current, row):
    if row.get("handoff"):
        effect, reason = HANDOFFS[row["handoff"]]
        return effect, reason, "cue"
    if current["artifact"] == "type-title" and previous["artifact"] != "type-title":
        return "push-down", "Un título introduce una sección tras el contenido anterior.", "inferred"
    return None


def plan_transitions(rows, scenes, options, transitions, fps):
    joins = len(scenes) - 1
    budget = max(1, joins // options["joins_per_effect"]) if joins and options["mode"] != "cuts-only" else 0
    # Baseline assumes single-frame cuts. Subtract the earlier cut frame when
    # measuring free reading time from the end of one motion to the next start.
    baseline = [0]
    for index, scene in enumerate(scenes[:-1]):
        baseline.append(baseline[-1] + int(index > 0) + scene["reveal"] + scene["hold"])

    def spacing_problem(index, selected):
        for other in sorted(selected):
            a, b = sorted((index, other))
            if b-a < 3:
                return f"Se necesitan dos cortes entre {scenes[a]['id']} y {scenes[b]['id']}."
            free_frames = baseline[b] - baseline[a] - 1
            if free_frames < options["min_gap_seconds"] * fps:
                return (f"Hay {free_frames/fps:.2f} s entre el fin del efecto de {scenes[a]['id']} "
                        f"y el inicio del de {scenes[b]['id']}; se requieren {options['min_gap_seconds']} s.")
        return ""

    explicit = [i for i in range(1, len(rows)) if rows[i].get("transition", {}).get("id", "cut") != "cut"]
    require(len(explicit) <= budget,
            f"Exceso de transiciones con movimiento: se solicitaron {len(explicit)} para {joins} uniones "
            f"y el presupuesto es {budget}. Usa cortes en las uniones ordinarias.")
    selected = set()
    for i in explicit:
        problem = spacing_problem(i, selected)
        require(not problem, problem)
        selected.add(i)

    candidates = []
    decisions = {}
    for i in range(1, len(rows)):
        row, previous, current = rows[i], scenes[i-1], scenes[i]
        if "transition" in row:
            decisions[i] = ("explicit", row["transition"].get("reason") or
                            (HANDOFFS[row["handoff"]][1] if row.get("handoff") else "Elección explícita de la receta."))
            continue
        decisions[i] = ("default", "Continuar la lectura con un corte.")
        if preserves_data_anchor(previous, current):
            decisions[i] = ("continuity", "La cifra y la barra destacan el mismo dato. Conservar la atención en ese valor.")
            continue
        if options["mode"] == "cuts-only" or len(scenes) < 4:
            continue
        candidate = handoff_candidate(previous, current, row)
        if candidate:
            effect, reason, origin = candidate
            if effect in transitions:
                candidates.append((origin != "cue", i, effect, reason, origin))

    # Reserve authored effects first. Among the remaining candidates prefer the
    # editor's semantic cues, then consider inferred matches in story order.
    for _, i, effect, reason, origin in sorted(candidates):
        if len(selected) >= budget:
            decisions[i] = ("default", "Corte para respetar el presupuesto de movimientos.")
            continue
        problem = spacing_problem(i, selected)
        if problem:
            decisions[i] = ("default", problem)
            continue
        scenes[i]["transition"] = effect
        scenes[i]["bridge"] = round(2.2 * fps)
        decisions[i] = (origin, reason)
        selected.add(i)

    cursor = 0
    audit = []
    for i, scene in enumerate(scenes):
        scene["start"] = cursor
        if i:
            origin, reason = decisions[i]
            audit.append({"from": scenes[i-1]["id"], "to": scene["id"], "id": scene["transition"],
                          "origin": origin, "reason": reason, "start_frame": cursor,
                          "duration_frames": scene["bridge"]})
        cursor += scene["bridge"] + scene["reveal"] + scene["hold"]
        scene["end"] = cursor
    return {"policy": options, "joins": joins, "effect_budget": budget, "styled": len(selected),
            "cuts": joins - len(selected), "decisions": audit}


def asset_descriptor(value):
    item = {"path": value} if isinstance(value, str) else value
    require(isinstance(item, dict) and set(item) <= {"path","fit","focal","in_s","out_s","still_s"} and
            isinstance(item.get("path"), str) and item["path"].strip(), "Medio sin ruta local válida")
    suffix=Path(item["path"]).suffix.lower()
    video=suffix in {".mp4",".webm"}
    require(video or suffix in {".png",".jpg",".jpeg",".webp"}, "Formato de medio local no admitido: "+suffix)
    fit=item.get("fit","cover")
    focal=item.get("focal",[.5,.5])
    require(fit in ("cover","contain") and isinstance(focal,list) and len(focal)==2 and
            all(number(n) and n<=1 for n in focal),"Usa fit cover/contain y focal [x,y] entre 0 y 1")
    if "still_s" in item:
        require(video and number(item["still_s"]) and not ({"in_s","out_s"} & item.keys()),
                "still_s necesita segundos desde el inicio del archivo de vídeo y se usa sin in_s/out_s")
        kind = "video-frame"
    elif video:
        require(number(item.get("in_s",0)) and ("out_s" not in item or
                (number(item["out_s"]) and item["out_s"]>item.get("in_s",0))),"Los límites del clip deben avanzar")
        kind = "video"
    else:
        require(not ({"in_s","out_s"} & item.keys()),"Los tiempos in_s/out_s son exclusivos del vídeo")
        kind = "image"
    return {**item,"fit":fit,"focal":focal,"kind":kind}


def media_references(value):
    if isinstance(value,dict):
        for key,child in value.items():
            if key in {"media","mark","slide","background"} and isinstance(child,str):
                yield child
            else:
                yield from media_references(child)
    elif isinstance(value,list):
        for child in value:
            yield from media_references(child)


def compile_recipe(spec, defaults, transitions, builtin_media=()):
    require(isinstance(spec,dict) and not set(spec)-{"version","fps","width","height","assets","scenes","transition_policy"}, "Receta con campos desconocidos")
    policy = transition_policy(spec)
    require(type(spec.get("version")) is int and spec["version"]==1, "Se requiere version 1")
    fps=spec.get("fps",24)
    require(type(fps) is int and 12<=fps<=60, "fps debe estar entre 12 y 60")
    w,h=spec.get("width",1280),spec.get("height",720)
    require(all(type(n) is int and n>=2 and n%2==0 for n in [w,h]), "Se requieren dimensiones pares positivas")
    assets=spec.get("assets",{})
    require(isinstance(assets,dict) and all(isinstance(k,str) and k and not k.startswith("@") for k in assets), "assets mapea nombres a medios locales")
    descriptors={key:asset_descriptor(value) for key,value in assets.items()}
    rows=spec.get("scenes")
    require(isinstance(rows,list) and len(rows)>0,"Se requiere al menos una escena")
    scenes, seen, signatures = [],set(),[]
    for i,s in enumerate(rows):
        require(isinstance(s,dict) and not set(s)-{"id","artifact","props","hold","transition","return_reason","handoff"},f"Escena {i+1}: campos desconocidos")
        sid=s.get("id")
        require(isinstance(sid,str) and re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*",sid) and sid not in seen,f"ID de escena duplicado o no válido: {sid}")
        seen.add(sid)
        kind=s.get("artifact")
        require(isinstance(kind,str) and kind in defaults and kind in FIELDS,f"{sid}: artefacto desconocido")
        props=s.get("props",defaults[kind])
        if kind == "module-transfer" and isinstance(props, dict):
            port_defaults = {key: defaults[kind][key] for key in ("inputs", "outputs", "highlightIndex")}
            props = {**port_defaults, **props}
        check_props(kind,props,set(assets)|set(builtin_media))
        signature=json.dumps([kind,props],sort_keys=True,ensure_ascii=False)
        require(not signatures or signature!=signatures[-1],f"{sid}: escena duplicada consecutiva")
        if len(signatures)>=2 and signatures[-2]==signature:
            require(isinstance(s.get("return_reason"),str) and s["return_reason"].strip(),f"{sid}: retorno A→B→A sin motivo editorial (return_reason)")
        signatures.append(signature)
        tr=s.get("transition",{"id":"cut"})
        require(isinstance(tr,dict) and not set(tr)-{"id","seconds","reason"} and isinstance(tr.get("id"),str) and tr["id"] in transitions, f"{sid}: transición desconocida")
        require("reason" not in tr or isinstance(tr["reason"], str) and tr["reason"].strip(), f"{sid}: reason debe explicar el propósito")
        require("handoff" not in s or isinstance(s["handoff"],str) and s["handoff"] in HANDOFFS, f"{sid}: handoff debe ser section, comparison o detail")
        require(i>0 or not {"transition","handoff"} & s.keys(), "La primera escena no tiene plano anterior")
        seconds=tr.get("seconds",1/fps if tr["id"]=="cut" else 2.2)
        require(number(seconds) and seconds>0, f"{sid}: duración de transición inválida")
        if tr["id"]=="cut": require(seconds<=1/fps+.000001, f"{sid}: el corte ocupa un fotograma")
        else: require(seconds>=1.0,f"{sid}: reserva al menos 1 s para poder seguir el movimiento")
        bridge=(1 if tr["id"]=="cut" else round(seconds*fps)) if i else 0
        read_min=max(2.5,words(props)/3)
        hold=s.get("hold",max(3.0,math.ceil(read_min*10)/10))
        require(number(hold) and hold>=read_min, f"{sid}: reserva al menos {read_min:.2f} s de lectura después de la entrada")
        reveal=math.ceil(reveal_time(kind,props)*fps)
        videos=sorted({k for k in media_references(props) if k in descriptors and descriptors[k]["kind"]=="video"})
        scenes.append(dict(id=sid,artifact=kind,props=props,video_assets=videos,transition=tr["id"],bridge=bridge,
                           reveal=reveal,hold=math.ceil(hold*fps)))
    audit = plan_transitions(rows, scenes, policy, transitions, fps)
    for scene in scenes:
        if scene["artifact"] != "guest-grid":
            continue
        moving = sum(guest["media"] in scene["video_assets"] for guest in scene["props"]["guests"])
        require(moving <= 3, f"{scene['id']}: cuatro paneles reproducirían vídeo a la vez. "
                "Elige un retrato o un fotograma con still_s para una de las cuatro personas.")
        require(moving < 3 or scene["bridge"] <= 1, f"{scene['id']}: la transición y tres vídeos sumarían cuatro movimientos. "
                "Usa un corte o elige una imagen o still_s para otro panel.")
    return dict(fps=fps,width=w,height=h,frames=scenes[-1]["end"],scenes=scenes,transition_audit=audit)
