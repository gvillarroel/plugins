"""Bind observed counts and paired measurements to marks on a common scale."""
from recommend_motion import MISSING, number_value


def measured_chart(rows, fields, request, relation):
    rate = relation == "rate-comparison"
    roles = ("category", "numerator", "denominator") if rate else ("item", "before", "after")
    columns = [fields[role] for role in roles]
    if len(set(columns)) != 3 or not 2 <= len(rows) <= 8:
        raise ValueError("Asigna tres columnas distintas y de dos a ocho entidades por plano.")
    units = {row.get(fields["unit"]) for row in rows} if "unit" in fields else set()
    if "unit" in request:
        units.add(request["unit"])
    if not rate and (len(units) != 1 or not all(isinstance(u, str) and u.strip() for u in units)):
        raise ValueError("Ambos extremos deben expresar la misma unidad.")
    chart = dict(kind="comparison", encoding=relation, locale="es-ES", unit="%" if rate else units.pop(),
                 duration=max(2, request.get("duration", 6)), records=[])
    if request.get("title"):
        chart["title"] = request["title"]
    names = set()
    for i, row in enumerate(rows, 1):
        name = row.get(columns[0])
        if not isinstance(name, str) or not name.strip() or name.strip() in names:
            raise ValueError("Cada fila necesita una identidad única.")
        names.add(name.strip())
        record = dict(id=f"r{i}", label=name.strip())
        for role, column in zip(roles[1:], columns[1:]):
            if column not in row:
                raise ValueError(f"Falta la columna {column} en la fila {i}.")
            raw = row[column]
            missing = raw is None or isinstance(raw, str) and raw.strip().casefold() in MISSING
            value = None if missing else number_value(raw)
            if not missing and (value is None or abs(value) > 1e9):
                raise ValueError(f"Medida inválida en {column}, fila {i}.")
            record[role] = value
        if rate:
            part, total = record["numerator"], record["denominator"]
            if any(n is not None and (n < 0 or int(n) != n) for n in (part, total)) or (
                    part is not None and total is not None and part > total):
                raise ValueError("Una frecuencia de casos necesita recuentos enteros y una parte contenida en su base.")
            record["value"] = round(100 * part / total, 2) if part is not None and total else None
        else:
            record["value"] = record["after"]
        if record["label"] == request.get("focus"):
            chart["focus"] = record["id"]
        chart["records"].append(record)
    if "focus" in request and "focus" not in chart:
        raise ValueError("La entidad destacada debe existir en la fuente.")
    return chart
