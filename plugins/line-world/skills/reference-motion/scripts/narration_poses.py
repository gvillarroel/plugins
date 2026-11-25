"""Bind semantic diagram poses to a local voice clock, preserving the original choreography."""
import math


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(x):
    return type(x) in (int,float) and math.isfinite(x)


def unit(x):
    return finite(x) and 0 <= x <= 1


def validate_clock(props, kind):
    if "poseClock" in props:
        knots=props["poseClock"]
        require(isinstance(knots,list) and len(knots)>=2 and all(
            isinstance(k,list) and len(k)==2 and all(unit(v) for v in k) for k in knots),
            "poseClock requiere pares [tiempo normalizado, pose normalizada].")
        require(knots[0]==[0,0] and knots[-1]==[1,1] and all(
            a[0]<b[0] and a[1]<=b[1] for a,b in zip(knots,knots[1:])),
            "El reloj debe recorrer todas las poses en orden.")
    if "poseFocus" in props:
        require(kind=="staged-network" and isinstance(props["poseFocus"],list),"poseFocus requiere una red editable.")
        ids={n["id"] for n in props["nodes"]}
        for cue in props["poseFocus"]:
            require(isinstance(cue,list) and len(cue)==3 and isinstance(cue[0],str) and cue[0] in ids
                    and unit(cue[1]) and unit(cue[2]) and cue[1]<cue[2],
                    "El énfasis requiere un nodo identificado y un intervalo dentro de la escena.")
    if "poseLabels" in props:
        if kind=="staged-network": ids={n["id"] for n in props["nodes"]}
        else: ids={f"message-{i+1}" for i in range(len(props.get("exchanges",[])))}
        gates=props["poseLabels"]
        require(isinstance(gates,dict) and all(k in ids and unit(t) for k,t in gates.items()),
                "poseLabels requiere identificadores de rótulo y tiempos normalizados.")


def cue_list(narration):
    require(isinstance(narration,dict) and set(narration)<={"duration_s","audio","words","cues","timing_source"},
            "narration contiene campos desconocidos.")
    duration=narration.get("duration_s")
    require(finite(duration) and duration>0,"narration.duration_s debe ser la duración de la voz.")
    if "audio" in narration:
        require(isinstance(narration["audio"],str) and narration["audio"].strip(),"audio requiere una ruta local.")
    words=narration.get("words",[])
    require(isinstance(words,list) and all(isinstance(w,dict) and set(w)=={"text","start_s"} and
            isinstance(w["text"],str) and w["text"].strip() and finite(w["start_s"]) and
            0<=w["start_s"]<duration for w in words),"words requiere text y start_s por palabra.")
    require(all(a["start_s"]<=b["start_s"] for a,b in zip(words,words[1:])),"Las palabras deben estar en orden.")
    supplied=narration.get("cues")
    require(isinstance(supplied,list) and supplied,"Indica al menos una mención para sincronizar.")
    cues=[]
    for item in supplied:
        require(isinstance(item,dict) and set(item)<={"target","role","mention_s","word_index","offset_s","pose","hold_s"}
                and isinstance(item.get("target"),str) and item["target"].strip(),"Cada cue necesita un target.")
        require(("word_index" in item)!=("mention_s" in item),"Indica mention_s o word_index en cada cue.")
        cue=dict(item)
        if "word_index" in cue:
            i=cue["word_index"]
            require(type(i) is int and 0<=i<len(words),"word_index fuera de la locución.")
            cue.update(mention_s=words[i]["start_s"],word=words[i]["text"])
        mention=cue["mention_s"]
        offset=cue.get("offset_s",0)
        require(finite(mention) and 0<=mention<duration and finite(offset) and 0<=mention+offset<duration,
                "La mención y su pose deben estar dentro de la locución.")
        require(cue.get("role") in (None,"context","enter","readable","action","result","emphasis"),"Rol de pose desconocido.")
        require("pose" not in cue or unit(cue["pose"]), "pose debe ser una fracción del movimiento.")
        require("hold_s" not in cue or (cue.get("role") in ("emphasis","result") and finite(cue["hold_s"]) and cue["hold_s"]>0),
                "hold_s requiere un resultado o énfasis con duración positiva.")
        cue["visual_s"]=mention+offset
        cues.append(cue)
    return duration,cues


def name(s):
    return " ".join(s.split()).casefold()


def resolve(kind,props,cue):
    target=cue["target"]
    role=cue.get("role")
    if "pose" in cue:
        require(role not in ("context","emphasis"),"Usa pose para un cambio dibujado, o selecciona el nodo por identidad.")
        return role or "action",cue["pose"],None
    if kind == "trajectory-trace":
        samples = props["samples"]
        by_id = {f"sample-{i+1}":s for i,s in enumerate(samples)}
        require(target in by_id, "Selecciona la muestra por sample-1, sample-2, etc.")
        if target == "sample-1" and role in (None, "context"):
            return "context", None, None
        require(role in (None, "result"), "Cada muestra identifica el instante de llegada de ambas marcas.")
        first, last = samples[0]["t"], samples[-1]["t"]
        return "result", (by_id[target]["t"]-first)/(last-first), None
    if kind == "interval-refinement":
        intervals = props["intervals"]
        found = [i for i, step in enumerate(intervals) if target == f"interval-{i+1}"]
        if not found:
            found = [i for i, step in enumerate(intervals) if name(step["label"]) == name(target)]
        require(len(found) == 1, "Selecciona la etapa por su nombre único o por interval-1, interval-2, etc.")
        i = found[0]
        if i == 0:
            require(role in (None, "context"), "La escala inicial está visible desde el primer fotograma.")
            return "context", None, None
        role = role or "result"
        require(role in ("action", "result"), "Selecciona el comienzo de la selección o la llegada de la ampliación.")
        outward = intervals[1]["low"] < intervals[0]["low"] or intervals[1]["high"] > intervals[0]["high"]
        if outward:
            phase = .16 if role == "action" else .48
        else:
            phase = .13 if role == "action" else .84
        return role, (i - 1 + phase) / (len(intervals) - 1), None
    if kind=="staged-network":
        nodes=props["nodes"]
        match=[n for n in nodes if n["id"]==target] or [n for n in nodes if name(n["label"])==name(target)]
        if not match:
            path=[e for e in props["edges"] if f"{e['from']}->{e['to']}"==target]
            if len(path)==1 and role in ("action","result"):
                e=path[0]; span=e.get("token") or e.get("enter")
                require(span is not None,"Este enlace carece de un recorrido animado.")
                return role,span[int(role=="result")],None
        require(len(match)==1,f"«{target}» debe identificar un solo nodo o recorrido. Usa su id en la receta.")
        n=match[0]
        span=n.get("enter",[0,0])
        role=role or ("context" if span[1]==0 else "readable")
        if role=="emphasis": return role,None,n
        if role=="context":
            require(span[1]==0,"El contexto inicial debe estar visible en la pose de apertura.")
            return role,None,n
        if role in ("enter","readable"):
            require(span[1]>0,"El elemento ya estaba visible. Selecciona contexto o énfasis.")
            return role,span[int(role=="readable")],n
        move=n.get("moveFrom")
        require(move is not None,"La figura carece de desplazamiento. Selecciona entrada, énfasis o un enlace.")
        return role,move[2 if role=="action" else 3],n
    if kind=="message-ladder":
        if target in props["labels"] and role in (None,"context"):
            return "context",None,None
        rows=props["exchanges"]
        indices=[i for i,row in enumerate(rows) if target==f"message-{i+1}"] or [
            i for i,row in enumerate(rows) if name(row["label"])==name(target)]
        require(len(indices)==1,"Elige un turno por su texto o por message-1, message-2, etc.")
        role=role or "readable"
        require(role in ("enter","readable","action","result"),"Rol no disponible para este turno.")
        # The Canvas draws the message after eased progress > .47. Halfway through
        # the path it is present, and at the end the arrow reaches the recipient.
        step=(.885-.065)/len(rows)
        return role,.065+indices[0]*step+{"enter":0,"action":0,"readable":.42,"result":.84}[role]*step,{"id":f"message-{indices[0]+1}"}
    raise ValueError("Indica la pose normalizada del mecanismo que corresponde a esta mención.")


def pose_at(knots,t):
    for (a,p),(b,q) in zip(knots,knots[1:]):
        if t<=b: return p+(q-p)*(t-a)/(b-a)
    return 1


def bind(scene,narration,fps):
    from motion_recipe import DIAGRAM_KINDS
    duration,cues=cue_list(narration)
    props=scene["props"];kind=scene["artifact"]
    require(kind in DIAGRAM_KINDS,"Esta representación necesita partitura en su productor especialista.")
    native_duration=props.get("duration",5)
    points=[[0,0],[1,1]]
    focuses=[]
    label_gates={}
    audit=[]
    for cue in cues:
        role,pose,node=resolve(kind,props,cue)
        t=cue["visual_s"]/duration
        if role=="emphasis":
            end_s=min(duration,cue["visual_s"]+cue.get("hold_s",.8))
            require(end_s-cue["visual_s"]>=1/fps,"La voz no deja un fotograma completo para el énfasis.")
            focuses.append((node,t,end_s/duration))
        elif pose is not None or (kind=="trajectory-trace" and role=="context"):
            position = 0 if pose is None else pose
            if kind in ("interval-refinement","trajectory-trace"):
                # A measured extremum can be present for just one sample. Land on an exported frame.
                t = min(1,math.ceil(cue["visual_s"]*fps-1e-9)/(fps*duration))
            points.append([t,position])
            if role=="result" and "hold_s" in cue:
                end = t + cue["hold_s"]/duration
                require(end <= 1, "La pausa del resultado debe caber en la locución.")
                points.append([end,position])
        if role=="readable" and node:
            require(node["id"] not in label_gates,"Para volver a mencionar un rótulo ya leído usa énfasis.")
            label_gates[node["id"]]=t
        audit.append({**cue,"role":role,"pose":pose,"check":"already-visible" if role=="context" else "pose",
                      "frame":math.ceil(cue["visual_s"]*fps-1e-9)})
    knots=[]
    for pair in sorted(points):
        if not knots or pair!=knots[-1]: knots.append(pair)
    output={**props,"duration":duration,"poseClock":knots}
    if focuses:
        output["poseFocus"]=[[n["id"],a,b] for n,a,b in focuses]
    if label_gates: output["poseLabels"]=label_gates
    validate_clock(output,kind)
    for n,a,_ in focuses:
        require(pose_at(knots,a)+1e-8>=n.get("enter",[0,0])[1],
                f"«{n['label']}» aún no es legible al enfatizarla. Marca primero su entrada o lectura.")
    scene["props"]=output
    return {"status":"bound","fps":fps,"duration_s":duration,"original_motion_s":native_duration,
            "timing_source":narration.get("timing_source","Marcas suministradas por el autor"),
            "cues":audit,"pose_clock":knots}
