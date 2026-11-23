# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "playwright>=1.45"]
# ///
"""Build an editable, source-backed comparison of a portrait, a shot and a sequence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image


HERE = Path(__file__).resolve().parent
VIDEO = HERE.parents[2]
MEDIA_REGISTRY = VIDEO.parent / "reference-motion" / "assets" / "review-media.json"
FPS = 24
DURATION = 9
SOURCE_START = 1.75


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_assets(media, output):
    registry = json.loads(MEDIA_REGISTRY.read_text(encoding="utf-8"))
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("portrait-collins.png", "garden.mp4"):
        if sha(media / name) != registry[name]["sha256"]:
            raise ValueError(f"Unexpected source media for {name}. Check review-media.json.")
        shutil.copyfile(media / name, assets / name)
    shutil.copyfile(HERE / "leyenda.html", assets / "leyenda.html")
    (assets / "guia.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 16">'
        '<path d="M2 8H298" fill="none" stroke="#696969" stroke-width="2"/>'
        '<path d="M100 4V12 M200 4V12" fill="none" stroke="#696969" stroke-width="2"/>'
        '<rect y="6" x="2" height="4" width="0" fill="#9e1b32">'
        '<animate attributeName="width" from="0" to="296" dur="9s" fill="freeze"/></rect>'
        '<circle cy="8" cx="2" r="3.5" fill="#9e1b32">'
        '<animate attributeName="cx" from="2" to="298" dur="9s" fill="freeze"/></circle>'
        '</svg>\n', encoding="utf-8")
    frames = []
    for index in range(6):
        raw = subprocess.check_output([
            "ffmpeg", "-v", "error", "-ss", str(SOURCE_START + index / 2), "-i", str(assets / "garden.mp4"),
            "-frames:v", "1", "-vf", "scale=320:180", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1",
        ])
        frames.append(Image.frombytes("RGB", (320, 180), raw))
    frames[0].save(assets / "secuencia.gif", save_all=True, append_images=frames[1:], duration=500, loop=0, optimize=False)
    write_json(output / "fuentes.json", {name: registry[name] for name in ("portrait-collins.png", "garden.mp4")})
    return assets


def element(assets, kind, name, file, size, bounds, *, fit="contain", playback=None):
    x, y, width, height = bounds
    document = {
        "id": name, "assetId": name, "producerSkill": "repo-native",
        "fallbackReason": "The recipe prepares this element from its documented local source.",
        "kind": kind, "src": "assets/" + file, "sha256": sha(assets / file),
        "intrinsic": {"width": size[0], "height": size[1]},
        "bounds": dict(x=x, y=y, width=width, height=height), "zIndex": 10, "fit": fit,
        "overflow": "hidden", "background": "transparent", "clock": "static" if kind == "raster" else "master",
        "ports": [], "states": [],
    }
    if playback is not None:
        document["playback"] = playback
    return document


def track(element_id, prop, keyframes):
    return {"id": f"{element_id}-{prop.lower()}", "elementId": element_id, "property": prop, "keyframes": keyframes}


def gate(name, initial, *changes):
    keys = [{"at": 0, "value": initial}, *({"at": time, "value": value, "easing": "step-end"} for time, value in changes)]
    return track(name, "opacity", keys)


def scene(assets, width, height):
    portrait = width < height
    picture = (.07, .07, .86, .47) if portrait else (.54, .10, .41, .80)
    legend = (.07, .60, .86, .32) if portrait else (.055, .17, .43, .64)
    guide = (.07, .555, .86, .022) if portrait else (.54, .908, .41, .034)
    elements = [
        element(assets, "raster", "retrato", "portrait-collins.png", (512, 512), picture),
        element(assets, "video", "plano", "garden.mp4", (960, 540), picture, playback={"offsetSeconds": SOURCE_START - 3, "loop": False}),
        element(assets, "gif", "secuencia", "secuencia.gif", (320, 180), picture, playback={"mode": "decoded", "offsetSeconds": -6, "loop": False}),
        element(assets, "html", "leyenda", "leyenda.html", (360, 300), legend),
        element(assets, "svg", "guia", "guia.svg", (300, 16), guide, fit="stretch"),
    ]
    tracks = [gate("retrato", 1, (3, 0)), gate("plano", 0, (3, 1), (6, 0)), gate("secuencia", 0, (6, 1))]
    tracks.append(track("retrato", "scale", [{"at": 0, "value": .93}, {"at": 2.3, "value": 1, "easing": "ease-out"}]))
    divisor = math.gcd(width, height)
    return {
        "schemaVersion": 1, "id": "foto-plano-secuencia",
        "canvas": {"width": width, "height": height, "fps": FPS, "durationSeconds": DURATION,
                   "aspectRatio": f"{width // divisor}:{height // divisor}", "background": "#f7f7f7",
                   "safeArea": dict.fromkeys(("top", "right", "bottom", "left"), 16)},
        "masterClock": {"mode": "deterministic", "loop": False}, "elements": elements,
        "events": [], "tracks": tracks, "interactions": [],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--media-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--portrait", action="store_true")
    parser.add_argument("--channel", help="Chromium channel for capture, e.g. msedge")
    parser.add_argument("--build-only", action="store_true")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets = build_assets(args.media_dir.resolve(), output)
    width, height = (390, 844) if args.portrait else (800, 450)
    contract = scene(assets, width, height)
    write_json(output / "escena.json", contract)
    html = output / "src" / "index.html"
    scripts = VIDEO / "scripts"
    subprocess.run([sys.executable, str(scripts / "build_composite_scene.py"), str(output / "escena.json"),
                    str(html), "--project-root", str(output), "--report", str(output / "composicion.json"), "--force"], check=True)
    if not args.build_only:
        command = [sys.executable, str(scripts / "capture_html_video.py"), "--html", str(html), "--project-root", str(output),
                   "--output", str(output / "ejemplo.mp4"), "--manifest", str(output / "captura.json"),
                   "--fps", str(FPS), "--duration", str(DURATION), "--video-id", contract["id"],
                   "--width", str(width), "--height", str(height)]
        if args.channel:
            command.extend(["--channel", args.channel])
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL)
    print(output)


if __name__ == "__main__":
    main()
