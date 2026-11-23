# /// script
# requires-python = ">=3.11"
# dependencies = ["Pillow>=11,<13"]
# ///
"""Stress different editorial inputs and sizes, one fully decoded film at a time."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from direction import read

HERE = Path(__file__).resolve().parent


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--out", required=True, type=Path)
    args = cli.parse_args()
    args.out.mkdir(exist_ok=True, parents=True)
    rows = []
    for w, h in ((390, 844), (720, 1280), (1280, 720), (1920, 1080)):
        spec = read(HERE.parent / "assets/temperatura.json")
        spec["size"] = [w, h]
        if w == 720:
            spec["scenes"][2].update(
                title="Dos intervalos sin precipitación", values=[0, 0]
            )
        elif w == 1280:
            spec["scenes"][1].update(
                title="Temperatura estable durante la madrugada", values=[0, 0, 0, 0]
            )
            spec["scenes"][2].update(
                title="Dos magnitudes con órdenes de tamaño diferentes",
                values=[99.95, 0.0625],
            )
        elif w == 1920:
            spec["scenes"][2].update(
                title="Desviaciones respecto de la temperatura de referencia",
                values=[-1.125, 2.75],
                unit="°C",
            )
        recipe = args.out / f"receta-{w}.json"
        recipe.write_text(
            json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        out = args.out / f"estacion-{w}.mp4"
        subprocess.run(
            [sys.executable, str(HERE / "direction.py"), str(recipe), "-o", str(out)],
            check=True,
        )
        receipt = json.loads(out.with_suffix(".json").read_text())
        rows.append(
            {
                k: receipt[k]
                for k in (
                    "size",
                    "frames",
                    "measuredPeak",
                    "maxDecodedRgbError",
                    "exactBackwardSeeks",
                    "flatPaletteSamples",
                    "mp4Sha256",
                )
            }
        )
    (args.out / "matriz.json").write_text(
        json.dumps(rows, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
