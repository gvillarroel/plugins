# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy>=2,<3", "Pillow>=11,<13"]
# ///
"""Exercise signed values, true scale, legibility and reading holds across reproducible briefs."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import random
import time

import numpy as np
from PIL.ImageColor import getrgb

import brief_to_video as producer
from direction import GRAY, RED, RULE, frame, number


EXAMPLES = (
    ("Temperatura", "Al abrir", "Al cerrar", "°C", "grados Celsius"),
    ("Altitud", "Cota norte", "Cota sur", "m", "metros"),
    ("Saldo diario", "Día anterior", "Día actual", "EUR", "euros"),
    ("Desviación del nivel", "Marca inicial", "Marca final", "cm", "centímetros"),
    ("Retraso sobre el objetivo", "Primera medición", "Segunda medición", "ms", "milisegundos"),
)
CASES = ("ganancia", "pérdida", "ambos negativos", "cruce ascendente", "cruce descendente",
         "iguales", "dos ceros", "desde cero", "hasta cero", "escalas dispares")


def sample(rng, index):
    subject, first, second, unit, spoken = rng.choice(EXAMPLES)
    scale = 10 ** rng.randrange(3)
    a, b = sorted(rng.sample(range(1, 500), 2))
    pair = [(a,b),(b,a),(-b,-a),(-a,b),(b,-a),(a,a),(0,0),(0,b),(-a,0),(1,2500)][index % len(CASES)]
    values = [value / scale for value in pair]
    return {
        "version": 1, "subject": subject, "title": "Dos mediciones",
        "source": {"type": "simulated", "detail": "Mediciones de prueba"},
        "measures": [{"label": label, "value": value, "unit": unit} for label,value in zip((first, second), values)],
        "spokenUnit": spoken, "takeaway": "La diferencia es {gap}",
        "narration": ["El primer valor es {a} y el segundo es {b}.", "La diferencia entre ambos es {gap}."],
    }


def bounds(mask):
    positions = np.flatnonzero(mask)
    return (int(positions[0]), int(positions[-1]) + 1) if positions.size else None


def inspect(brief, kind):
    visual, voice = producer.compile_brief(brief, producer.SIZES[kind])
    scene, reading = visual["scenes"]
    values = [Decimal(str(row["value"])) for row in brief["measures"]]
    low, high = min(0, *values), max(0, *values)
    span = high - low or 1
    expected_gap = number(abs(values[1] - values[0])) + " " + brief["spokenUnit"]
    if expected_gap not in voice[1] or voice[0].count("menos ") != sum(value < 0 for value in values):
        raise ValueError("La locución cambia el signo o la diferencia.")
    wrap = 32 if kind == "vertical" else 42
    for phrase in voice:
        blocks = producer.caption_blocks(phrase, wrap, brief["spokenUnit"])
        if " ".join(" ".join(blocks).split()) != phrase or any(len(line) > wrap for block in blocks for line in block.splitlines()):
            raise ValueError("Los subtítulos pierden palabras o sobrepasan el ancho.")

    before, _, _ = frame(visual, scene, 0)
    rows = before.info["comparisonRows"]
    scanlines = [round(row["y"]) for row in rows]
    reference = np.asarray(before)
    rails = []
    for y, row in zip(scanlines, rows):
        start, stop = row["labelBox"][2], row["valueBox"][0]
        run = bounds(np.all(reference[y, start:stop] == getrgb(RULE), axis=1))
        rails.append((run[0] + start, run[1] + start) if run else None)
    if not all(rails):
        raise ValueError("Falta la referencia de la escala.")
    previous = [0, 0]
    worst = 0.0
    for tick in (1, 6, 12, 18, 24):
        picture, _, _ = frame(visual, scene, tick)
        rgb = np.asarray(picture)
        for i, (y, role, value) in enumerate(zip(scanlines, (GRAY, RED), values)):
            left, right = rails[i]
            ink = bounds(np.all(rgb[y, left:right] == getrgb(role), axis=1))
            length = ink[1] - ink[0] if ink else 0
            if value and length < previous[i]:
                raise ValueError("Una barra retrocede durante el desarrollo.")
            previous[i] = length
            if tick == 24 and value:
                width = right - left
                origin = float(-low / span) * width
                wanted = float(value / span) * width
                edge_error = (max(abs(ink[0] - min(origin,origin+wanted)), abs(ink[1] - max(origin,origin+wanted)))
                              if ink else abs(wanted))
                worst = max(worst, edge_error)
                if edge_error > 2:
                    raise ValueError(f"Extremo de la barra {i+1} desviado {edge_error:.2f} px.")
            if tick == 24 and not value and length == 0:
                raise ValueError("El cero carece de marca visible.")
    still, _, _ = frame(visual, reading, 0)
    later, _, _ = frame(visual, reading, reading["hold"] - 1)
    if still.tobytes() != later.tobytes():
        raise ValueError("El gráfico cambia durante la lectura.")
    return worst


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cases", type=int, default=30)
    cli.add_argument("--seed", type=int, default=47)
    cli.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    if args.cases <= 0:
        cli.error("--cases debe ser positivo")
    rng = random.Random(args.seed)
    started = time.monotonic()
    report = {"schema": "line-world-comparison-audit-v1", "seed": args.seed, "briefs": args.cases,
              "complete": False, "tested": 0, "formats": list(producer.SIZES),
              "designs": {}, "maxBarEdgeErrorPixels": 0, "failures": 0, "firstFailures": []}
    if args.report.exists():
        previous = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not isinstance(previous, dict) or previous.get("schema") != report["schema"]:
            cli.error("Elige una ruta nueva para el informe.")
    args.report.parent.mkdir(parents=True, exist_ok=True)

    def checkpoint():
        report["seconds"] = round(time.monotonic() - started, 3)
        producer.narrated.write(args.report, report)

    for n in range(args.cases):
        brief = sample(rng, n)
        design = CASES[n % len(CASES)]
        report["designs"][design] = report["designs"].get(design, 0) + 1
        for kind in producer.SIZES:
            try:
                error = inspect(brief, kind)
                report["maxBarEdgeErrorPixels"] = max(report["maxBarEdgeErrorPixels"], round(error, 4))
            except ValueError as exc:
                report["failures"] += 1
                if len(report["firstFailures"]) < 10:
                    report["firstFailures"].append({"index": n, "format": kind, "error": str(exc), "brief": brief})
            report["tested"] += 1
        if (n + 1) % 250 == 0:
            checkpoint()
    report["ok"] = not report["failures"]
    report["complete"] = True
    checkpoint()
    print(f"{report['tested']} composiciones, {report['failures']} incidencias; {args.report}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
