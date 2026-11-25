"""Place directed relations on the same deterministic clock used by the film renderer."""
from collections import defaultdict


def relation_of(pairs):
    """Identify only unambiguous, connected forms. Parallel records can be distinct events."""
    if not pairs or any(a == b for a, b in pairs) or len(set(pairs)) != len(pairs):
        return None
    successors = defaultdict(list)
    parents = defaultdict(list)
    for a, b in pairs:
        successors[a].append(b)
        parents[b].append(a)
    if len(successors) == 1 and len(parents) > 1:
        return "fan-out"
    if len(parents) == 1 and len(successors) > 1:
        return "fan-in"
    roots = set(successors) - set(parents)
    if len(roots) != 1 or any(len(v) != 1 for v in parents.values()):
        return None
    visited = set()
    waiting = list(roots)
    while waiting:
        item = waiting.pop()
        if item in visited:
            return None
        visited.add(item)
        waiting.extend(successors.get(item, ()))
    if visited != set(successors) | set(parents):
        return None
    return "sequence" if all(len(v) == 1 for v in successors.values()) else "hierarchy"


def network(pairs, kind, duration):
    outgoing = defaultdict(list)
    for a, b in pairs:
        outgoing[a].append(b)
    entities = list(dict.fromkeys(value for pair in pairs for value in pair))
    ids = {value: f"n{i+1}" for i, value in enumerate(entities)}
    nodes, edges = [], []

    def node(value, x, y, w, h, **extras):
        nodes.append(dict(id=ids[value], label=value, x=x, y=y, w=w, h=h, **extras))

    def edge(a, b, start, span):
        edges.append({"from":ids[a], "to":ids[b], "enter":[start, start + span*.50],
                      "token":[start + span*.48, start + span*.87]})

    if kind in {"fan-in", "fan-out"}:
        if not 2 <= len(pairs) <= 6:
            raise ValueError("La fila de destinos admite de dos a seis ramas legibles.")
        outward = kind == "fan-out"
        hub = pairs[0][0 if outward else 1]
        node(hub, .23 if outward else .77, .5, .31, .14)
        step = .81/len(pairs)
        for i, (a, b) in enumerate(pairs):
            start = .075 + i*step
            y = .18 + .64*i/(len(pairs)-1)
            timing = [start + step*.26, start + step*.54] if outward else [start, start + step*.22]
            node(b if outward else a, .77 if outward else .23, y, .33, min(.112,.55/len(pairs)), enter=timing)
            edge(a, b, start + (0 if outward else step*.20), step*.80)
    else:
        root = next(a for a in outgoing if a not in {b for _, b in pairs})
        if kind == "sequence":
            if len(entities) > 5:
                raise ValueError("La secuencia supera cinco pasos en un solo plano.")
            ordered = [root]
            while outgoing.get(ordered[-1]):
                ordered.append(outgoing[ordered[-1]][0])
            step = .80/(len(ordered)-1)
            width = min(.25,.79/len(ordered))
            for i, value in enumerate(ordered):
                x = width/2 + .045 + i*(.91-width)/(len(ordered)-1)
                start = .08 + max(0,i-1)*step
                node(value, x, .50, width, .15, **({"enter":[start + step*.24, start + step*.55]} if i else {}))
                if i: edge(ordered[i-1], value, start, step)
        else:
            if len(entities) > 12:
                raise ValueError("El árbol supera doce entidades en el encuadre.")
            # Allocate disjoint horizontal spans to whole subtrees before placing the parents.
            leaves = [v for v in entities if not outgoing.get(v)]
            if len(leaves) > 5:
                raise ValueError("El árbol supera cinco hojas en una fila.")
            order, slot, depth = [], {}, {}
            def place(value, level):
                depth[value] = level
                children = outgoing.get(value, [])
                if children:
                    for child in children: place(child, level+1)
                    slot[value] = (slot[children[0]] + slot[children[-1]]) / 2
                else:
                    slot[value] = len(order)
                    order.append(value)
            place(root, 0)
            levels = max(depth.values())
            if levels > 3:
                raise ValueError("El árbol supera cuatro niveles legibles en el encuadre.")
            width = min(.26, .77/len(leaves))
            interval = .79/levels
            def opening(level): return .08 + (level-1)*interval
            for value in entities:
                level = depth[value]
                x = .14 + .72 * slot[value]/(len(leaves)-1)
                y = .17 + level*.67/levels
                start = opening(level)
                timing = {"moveFrom":[x,.34,.035,.20]} if not level else {"enter":[start+interval*.25,start+interval*.63]}
                node(value,x,y,width,.11,**timing)
            for a,b in pairs:
                edge(a,b,opening(depth[b]),interval)
    return {"nodes":nodes, "edges":edges, "duration":duration}
