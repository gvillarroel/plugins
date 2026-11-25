"""Adapt membership and paired qualitative observations to editable System Design diagrams."""
import hashlib
import json
import math
import unicodedata

from recommend_motion import MISSING, number_value

ABSENT_LABELS = MISSING - {"pendiente", "unknown"}


def _read_rows(rows, fields, roles, duration):
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("La duración debe ser un número positivo en segundos.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("La composición necesita al menos una fila con datos.")
    columns = [fields.get(role) for role in roles] if isinstance(fields, dict) else []
    if (len(columns) != len(roles) or not all(isinstance(k, str) and k.strip() for k in columns)
            or len(set(columns)) != len(columns)):
        raise ValueError(f"Asigna una columna distinta a cada campo: {', '.join(roles)}.")
    values = []
    for index, row in enumerate(rows, 1):
        record = []
        for role, col in zip(roles, columns):
            value = row.get(col) if isinstance(row, dict) else None
            if isinstance(value, bool) and role in {"before", "after"}:
                value = json.dumps(value)
            if type(value) is int and role in {"group", "item"}:
                value = str(value)
            if not isinstance(value, str) or value.strip().casefold() in ABSENT_LABELS:
                raise ValueError(f"La fila {index} requiere una etiqueta disponible en «{col}».")
            if role in {"before", "after"} and number_value(value) is not None:
                raise ValueError(f"«{col}» contiene una magnitud. Compara las medidas con una escala común.")
            record.append(value.strip())
        values.append(record)
    return values


def _id(role, *labels):
    key = json.dumps(labels, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"{role}-{hashlib.sha256(key).hexdigest()[:16]}"


def _em_width(text):
    # Conservative width in em for the bundled canvas font, including wide and combining characters.
    total = 0.0
    for char in text:
        if unicodedata.category(char) in ("Mn", "Me"):
            continue
        if unicodedata.east_asian_width(char) in ("W", "F") or char in "MWmw@%":
            total += 1
        elif char.isupper():
            total += .76
        else:
            total += .62
    return total


def _caption(text, width, size=19, lines=2):
    budget = width * 960 * .86 / size
    words = text.split()
    if not words:
        raise ValueError("Falta un rótulo que identifique la entidad.")
    wrapped = [words[0]]
    for word in words[1:]:
        candidate = wrapped[-1] + " " + word
        if _em_width(candidate) <= budget:
            wrapped[-1] = candidate
        else:
            wrapped.append(word)
    if len(wrapped) > lines or any(_em_width(line) > budget for line in wrapped):
        raise ValueError(f"«{text}» necesita más espacio de lectura. Abrevia su rótulo o divide el plano.")
    return "\n".join(wrapped)


def _node(role, identity, label, x, y, w, h, **options):
    return dict(id=_id(role, *identity), label=label, x=x, y=y, w=w, h=h, **options)


def grouped_rows(rows, fields, duration):
    """Reserve one band per observed group; reveal its recorded members after the frame."""
    values = _read_rows(rows, fields, ("group", "item"), duration)
    members = {}
    for group, item in values:
        bucket = members.setdefault(group, [])
        if item in bucket:
            raise ValueError(f"«{item}» se repite en «{group}». Asigna una identidad inequívoca a cada miembro.")
        bucket.append(item)
    columns = max(len(bucket) for bucket in members.values())
    if len(members) > 4 or columns > 4:
        raise ValueError("Se admiten hasta cuatro grupos y cuatro miembros por grupo. Divide los grupos entre planos.")

    gap = .024
    band_h = min(.238, (.86 - (len(members)-1)*gap)/len(members))
    first_y = .5 - (len(members)-1)*(band_h+gap)/2
    member_w = min(.31, (.82-(columns-1)*gap)/columns)
    member_h = min(.105, band_h-.075)
    beat = .90/len(members)
    nodes = []
    for i, (group, items) in enumerate(members.items()):
        y = first_y + i*(band_h+gap)
        start = i*beat
        enter_frame = {"enter": [start, start+beat*.22]} if i else {}
        nodes.append(_node("group", (group,), _caption(group,.86,17,1), .5,y,.91,band_h,
                           shape="group", **enter_frame))
        left = .5 - (len(items)*member_w+(len(items)-1)*gap)/2
        item_beat = beat*.68/len(items)
        for j, item in enumerate(items):
            enter = start+beat*.26+j*item_beat
            nodes.append(_node("member", (group,item), _caption(item,member_w),
                               left+member_w/2+j*(member_w+gap), y+.025, member_w,member_h,
                               fontSize=19, enter=[enter,enter+item_beat*.83]))
    return {"nodes":nodes, "edges":[], "duration":duration}


def parallel_rows(rows, fields, duration):
    """Keep each entity on one row while the second observation joins the first."""
    values = _read_rows(rows, fields, ("item", "before", "after"), duration)
    if len(values) > 6:
        raise ValueError("La comparación admite hasta seis entidades. Divide las filas entre planos.")
    if len({row[0] for row in values}) != len(values):
        raise ValueError("Cada fila comparada necesita una entidad distinta para emparejar sus estados.")

    first_x, second_x = .49, .805
    panel_w, cell_w = .303, .267
    row_h = min(.135, .64/len(values))
    first_y = .545-(len(values)-1)*row_h/2
    top = first_y-row_h/2-.093
    bottom = first_y+(len(values)-1)*row_h+row_h/2+.024
    nodes = []
    # Center the initial pair of columns, then move its headers and rows as a single
    # unit to accommodate the second condition, as in the paired system comparison.
    panel_y = (top+bottom)/2
    opening_offset = .14
    def opening(x, y):
        return [x+opening_offset, y, .40, .54]

    for key, x in (("before",first_x),("after",second_x)):
        header = _caption(fields[key],panel_w-.02,17,1)
        reveal = {"enter":[.54,.60]} if key == "after" else {"moveFrom":opening(x,panel_y)}
        nodes.append(_node("panel", (key,), header, x,panel_y,panel_w,bottom-top,
                           shape="group", **reveal))
    for i, (item, before, after) in enumerate(values):
        y = first_y+i*row_h
        first_start = .025+i*.34/len(values)
        reveal = {"enter":[first_start,first_start+.075]} if i else {}
        second_start = .61+i*.29/len(values)
        nodes.append(_node("entity", (item,), _caption(item,.272),.173,y,.272,row_h*.86,
                           shape="text", fontSize=19, moveFrom=opening(.173,y), **reveal))
        nodes.append(_node("before", (item,), _caption(before,cell_w),first_x,y,cell_w,row_h*.81,
                           fontSize=19, moveFrom=opening(first_x,y), **reveal))
        nodes.append(_node("after", (item,), _caption(after,cell_w),second_x,y,cell_w,row_h*.81,
                           fontSize=19, enter=[second_start,second_start+.07]))
    return {"nodes":nodes, "edges":[], "duration":duration}
