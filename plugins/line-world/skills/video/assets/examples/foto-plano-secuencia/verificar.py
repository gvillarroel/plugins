# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "playwright>=1.45"]
# ///
"""Verify an exported mixed-media movie against independently decoded source pixels."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageChops, ImageOps, ImageStat
from playwright.sync_api import sync_playwright

from generar import DURATION, FPS, SOURCE_START, VIDEO, sha, write_json

sys.path.insert(0, str(VIDEO / "scripts"))
from capture_html_video import serve_directory
from video_browser import launch_browser


def decoded(path, seconds):
    data = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(seconds), "-i", str(path),
                                   "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "pipe:1"])
    return Image.open(BytesIO(data)).convert("RGB")


def distance(a, b):
    return sum(ImageStat.Stat(ImageChops.difference(a.convert("RGB"), b.convert("RGB"))).mean) / 3


def region(frame, bounds):
    x, y, w, h = (bounds[k] for k in ("x", "y", "width", "height"))
    return frame.crop((round(x * frame.width), round(y * frame.height),
                       round((x + w) * frame.width), round((y + h) * frame.height)))


def actual_picture(frame, bounds, source):
    box = region(frame, bounds)
    resized = ImageOps.contain(source, box.size, Image.Resampling.BILINEAR)
    offset = ((box.width - resized.width) // 2, (box.height - resized.height) // 2)
    return box.crop((*offset, offset[0] + resized.width, offset[1] + resized.height)).resize((80, 64)), resized.resize((80, 64))


def check_browser(directory, scene, channel):
    size = {k: scene["canvas"][k] for k in ("width", "height")}
    records = []
    with serve_directory(directory) as origin, sync_playwright() as runtime:
        browser = launch_browser(runtime, channel=channel)
        try:
            page = browser.new_page(viewport=size)
            page.goto(origin + "/src/index.html")
            for at in (8.75, 2.5, 3.75, 6.75, 3.75):
                state = page.evaluate("t => window.renderConceptFrame(undefined, t)", at)
                label = page.frame_locator("iframe")
                title = label.locator("h1").inner_text()
                layout = label.locator("body").evaluate("""body => {
                    const rect = body.querySelector("#credit").getBoundingClientRect();
                    return {width: document.documentElement.scrollWidth, viewport: innerWidth,
                            bottom: rect.bottom, height: innerHeight};
                }""")
                source_time = state["elementStates"]["plano"]["videoTime"]
                records.append({"t": at, "title": title, "active": state["activeElementIds"], "videoTime": source_time,
                                "gifFrame": state["elementStates"]["secuencia"]["gifFrame"], "layout": layout,
                                "appearance": hashlib.sha256(page.screenshot()).hexdigest()})
        finally:
            browser.close()
    for row in records:
        index = int(row["t"] // 3)
        expected_ids = [{"retrato", "guia", "leyenda"}, {"plano", "guia", "leyenda"}, {"secuencia", "guia", "leyenda"}][index]
        row["ok"] = (set(row["active"]) == expected_ids and row["title"] == ["La fotografía", "El plano", "La secuencia"][index]
                     and row["layout"]["width"] <= row["layout"]["viewport"] and row["layout"]["bottom"] <= row["layout"]["height"])
    return {"ok": all(row["ok"] for row in records) and records[2]["appearance"] == records[4]["appearance"], "seeks": records}


def verify(directory, channel):
    scene = json.loads((directory / "escena.json").read_text(encoding="utf-8"))
    movie = directory / "ejemplo.mp4"
    assets = directory / "assets"
    bounds = scene["elements"][0]["bounds"]
    checks = []
    selected = []
    with Image.open(assets / "secuencia.gif") as gif:
        for time in [2.5, 3.25, 4, 5.75, *[6.25 + i / 2 for i in range(6)]]:
            frame = decoded(movie, time)
            if time < 3:
                with Image.open(assets / "portrait-collins.png") as still:
                    source = still.convert("RGB")
                kind = "retrato"
            elif time < 6:
                source = decoded(assets / "garden.mp4", SOURCE_START + time - 3)
                kind = "plano"
            else:
                gif.seek(int((time - 6) * 2))
                source = gif.convert("RGB")
                kind = "secuencia"
            actual, expected = actual_picture(frame, bounds, source)
            error = distance(actual, expected)
            background = frame.crop((0, 0, 10, 10))
            background_error = distance(background, Image.new("RGB", background.size, "#f7f7f7"))
            checks.append({"seconds": time, "kind": kind, "meanRGBError": round(error, 3),
                           "backgroundError": round(background_error, 3), "ok": error <= 7 and background_error <= 3})
            selected.append((kind, actual))
    motion = {}
    for kind in ("plano", "secuencia"):
        images = [im for selected_kind, im in selected if selected_kind == kind]
        motion[kind] = round(distance(images[0], images[-1]), 3)
    stream = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height,nb_frames,r_frame_rate", "-of", "json", str(movie)]))["streams"][0]
    size = scene["canvas"]
    correct_stream = (stream["width"], stream["height"], int(stream["nb_frames"]), stream["r_frame_rate"]) == (
        size["width"], size["height"], FPS * DURATION, f"{FPS}/1")
    browser = check_browser(directory, scene, channel)
    return {"ok": all(test["ok"] for test in checks) and correct_stream and browser["ok"] and min(motion.values()) > 2,
            "mp4Sha256": sha(movie), "stream": stream, "decodedSamples": checks, "sourceMotion": motion, "browser": browser}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--channel")
    args = parser.parse_args()
    directory = args.directory.resolve()
    result = verify(directory, args.channel)
    write_json(directory / "verificacion.json", result)
    print(json.dumps({"ok": result["ok"], "report": str(directory / "verificacion.json")}))
    raise SystemExit(0 if result["ok"] else 1)
