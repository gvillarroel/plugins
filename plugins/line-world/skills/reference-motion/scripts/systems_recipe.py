"""Validate editable layouts and the data used by the System Design study."""
import math


def require(ok, message):
    if not ok:
        raise ValueError(message)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def unit(value):
    return finite(value) and 0 <= value <= 1


def text(value):
    return isinstance(value, str) and bool(value.strip())


def interval(value, field):
    require(isinstance(value, list) and len(value) == 2 and all(unit(v) for v in value)
            and value[0] <= value[1], f"{field} requiere dos tiempos normalizados en orden")


def layout(props):
    nodes, edges = props.get("nodes"), props.get("edges")
    require(isinstance(nodes, list) and len(nodes) > 0, "staged-network.nodes requiere al menos una figura")
    require(isinstance(edges, list), "staged-network.edges requiere una lista de conexiones")
    ids = set()
    for node in nodes:
        required = {"id", "label", "x", "y", "w", "h"}
        require(isinstance(node, dict) and required <= node.keys()
                and set(node) <= required | {"shape", "enter", "active", "fontSize", "moveFrom"}, "Figura incompleta o desconocida")
        ident = node["id"]
        require(text(ident) and ident not in ids, "Cada figura requiere un id único")
        ids.add(ident)
        shape = node.get("shape", "box")
        require(shape in ("box", "circle", "server", "database", "person", "page", "group", "text"), "shape desconocida")
        require(isinstance(node["label"], str) and (shape != "text" or text(node["label"])), "Rótulo inválido")
        for pos, size in (("x","w"), ("y","h")):
            p, s = node[pos], node[size]
            require(unit(p) and unit(s) and s > 0 and p-s/2 >= -1e-7 and p+s/2 <= 1+1e-7,
                    f"{ident}: figura fuera del encuadre")
        if "fontSize" in node:
            require(finite(node["fontSize"]) and 8 <= node["fontSize"] <= 72,"fontSize entre 8 y 72")
        for field in ("enter", "active"):
            if field in node:
                interval(node[field], field)
        if "moveFrom" in node:
            move = node["moveFrom"]
            require(isinstance(move, list) and len(move) == 4 and all(unit(x) for x in move),
                    "moveFrom requiere x inicial, y inicial, inicio y fin normalizados")
            interval(move[2:], "moveFrom")
            require(all(size/2-1e-7 <= center <= 1-size/2+1e-7
                        for center,size in zip(move[:2], (node["w"], node["h"]))),
                    f"{ident}: posición inicial fuera del encuadre")
    for edge in edges:
        require(isinstance(edge,dict) and {"from","to"} <= edge.keys()
                and set(edge) <= {"from","to","label","enter","token","via","directed","dashed"}, "Conexión no válida")
        require(text(edge["from"]) and text(edge["to"]) and edge["from"] in ids and edge["to"] in ids
                and edge["from"] != edge["to"], "Conecta dos figuras distintas por id")
        via = edge.get("via", [])
        require(isinstance(via,list) and all(isinstance(v,list) and len(v)==2 and all(unit(x) for x in v) for v in via),
                "via requiere puntos normalizados")
        for field in ("directed","dashed"):
            require(field not in edge or type(edge[field]) is bool, f"{field} debe ser booleano")
        require("label" not in edge or isinstance(edge["label"],str), "La conexión requiere rótulo de texto")
        for field in ("enter","token"):
            if field in edge:
                interval(edge[field],field)


def validate_system(kind, props):
    if kind == "staged-network":
        layout(props)
    elif kind == "ring-handoff" and "keyLabel" in props:
        require(text(props["keyLabel"]), "keyLabel requiere una etiqueta")
    elif kind == "bit-probe" and "bits" in props:
        bits = props["bits"]
        require(isinstance(bits,dict) and set(bits) == {"size","groups"} and integer(bits["size"],6,16),
                "bits requiere size de 6 a 16 y tres grupos")
        groups = bits["groups"]
        require(isinstance(groups,list) and len(groups)==3 and all(
            isinstance(group,list) and 1<=len(group)<=4 and all(integer(i,0,bits["size"]-1) for i in group)
            and len(set(group))==len(group) for group in groups), "Índices de bits no válidos")
    elif kind == "message-ladder" and "exchanges" in props:
        rows=props["exchanges"]
        require(isinstance(rows,list) and 1<=len(rows)<=6 and all(
            isinstance(row,dict) and set(row)=={"label","from"} and text(row["label"])
            and integer(row["from"],0,1) for row in rows), "exchanges requiere 1–6 mensajes con origen 0 o 1")
    elif kind == "detail-callout":
        if "parts" in props:
            require(isinstance(props["parts"],list) and len(props["parts"])==4 and all(text(x) for x in props["parts"]),
                    "parts requiere cuatro fragmentos de texto")
        if "focusLabel" in props:
            require(text(props["focusLabel"]), "focusLabel requiere texto")
    elif kind == "radix-ladder":
        base=props.get("base",62)
        require(integer(base,2,62), "base debe estar entre 2 y 62")
        require(integer(props.get("value",11157),0,base**5-1), "value debe caber en cinco dígitos de la base indicada")
    elif kind == "queue-router":
        require("inputLabel" not in props or text(props["inputLabel"]), "inputLabel requiere texto")
        criteria = props.get("criteria", [])
        require(isinstance(criteria, list) and len(criteria) <= 3 and all(text(item) for item in criteria),
                "criteria admite hasta tres criterios de texto")
    elif kind == "token-gate":
        require(integer(props.get("tokens",1),0,5) and integer(props.get("requests",2),1,5),
                "tokens debe ser 0–5 y requests debe ser 1–5")
