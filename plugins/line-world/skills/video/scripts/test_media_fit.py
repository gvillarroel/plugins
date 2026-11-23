# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "playwright>=1.45"]
# ///
"""Compare rendered source fit and video clock modes against a pixel reference."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image, ImageDraw, ImageOps
from playwright.sync_api import sync_playwright

from build_composite_scene import build
from capture_html_video import serve_directory
from validate_scene_contract import validate_contract
from video_browser import launch_browser


PAPER = "#f7f7f7"
COLORS = ["#9e1b32", "#333e48", "#ff9633"]
FITS = ["contain", "cover", "none", "stretch"]
EXTENSIONS = {"raster": "png", "video": "mp4", "gif": "gif", "svg": "svg"}


def fixture(root):
    frames = []
    for index in range(2):
        source = Image.new("RGB", (36, 12))
        draw = ImageDraw.Draw(source)
        for i in range(3):
            draw.rectangle((i * 12, 0, i * 12 + 11, 11), fill=COLORS[(i + index) % 3])
        source.save(root / f"frame-{index}.png")
        frames.append(source)
    frames[0].save(root / "bars.png")
    frames[0].save(root / "bars.gif", save_all=True, append_images=frames[1:], duration=1000, loop=0)
    shapes = "".join(f'<rect x="{i * 12}" width="12" height="12" fill="{color}"/>' for i, color in enumerate(COLORS))
    (root / "bars.svg").write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 36 12">{shapes}</svg>', encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "1", "-i", str(root / "frame-%d.png"),
                    "-c:v", "libx264", "-g", "1", "-pix_fmt", "yuv420p", "-t", "2", str(root / "bars.mp4")], check=True)
    return frames


def scene(root):
    elements = []
    for row, (kind, ext) in enumerate(EXTENSIONS.items()):
        src = root / f"bars.{ext}"
        for col, fit in enumerate(FITS):
            identifier = f"{kind}-{fit}"
            item = {
                "id": identifier, "assetId": identifier, "producerSkill": "user-provided",
                "kind": kind, "src": src.name, "sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
                "intrinsic": {"width": 36, "height": 12}, "bounds": {"x": col/4, "y": row/4, "width": .25, "height": .25},
                "zIndex": 1, "fit": fit, "overflow": "hidden", "background": PAPER, "clock": "master", "ports": [],
            }
            if kind in {"gif", "video"}:
                item["playback"] = {"loop": col != 1, "offsetSeconds": .5}
                if kind == "gif":
                    item["playback"]["mode"] = "decoded"
            elements.append(item)
    return {"schemaVersion": 1, "id": "media-fit", "canvas": {"width": 192, "height": 192, "aspectRatio": "1:1",
            "fps": 12, "durationSeconds": 3, "background": PAPER, "safeArea": dict.fromkeys(("top", "left", "bottom", "right"), 0)},
            "masterClock": {"mode": "deterministic", "loop": False}, "elements": elements, "tracks": [], "events": [], "interactions": []}


def reference(source, fit):
    if fit == "stretch":
        return source.resize((48, 48))
    if fit == "cover":
        return ImageOps.fit(source, (48, 48))
    expected = Image.new("RGB", (48, 48), PAPER)
    plate = ImageOps.contain(source, (48, 48)) if fit == "contain" else source
    expected.paste(plate, ((48 - plate.width) // 2, (48 - plate.height) // 2))
    return expected


class MediaTest(unittest.TestCase):
    def test_pixel_fit_and_seek(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images = fixture(root)
            spec = scene(root)
            source = root / "spec.json"
            doc = root / "built" / "index.html"
            source.write_text(json.dumps(spec), encoding="utf-8")
            build(argparse.Namespace(contract=source, output=doc, project_root=root, allow_missing_hashes=False,
                                     require_producer_reports=False, force=False, report=None))
            bad = spec["elements"][4]["playback"]
            bad["loop"] = "false"
            bad["offsetSeconds"] = "0"
            issues = validate_contract(spec, root)["failures"]
            self.assertTrue(any("offsetSeconds" in s for s in issues))
            self.assertTrue(any(".loop" in s for s in issues))
            with serve_directory(root) as origin, sync_playwright() as runtime:
                browser = launch_browser(runtime)
                try:
                    page = browser.new_page(viewport={"width": 192, "height": 192})
                    page.goto(origin + "/built/index.html")
                    for at in (.25, 1.25, 2.25, .25):
                        page.evaluate("t => window.renderConceptFrame(undefined, t)", at)
                        raster = Image.open(BytesIO(page.screenshot())).convert("RGB")
                        for row, kind in enumerate(EXTENSIONS):
                            for col, fit in enumerate(FITS):
                                with self.subTest(t=at, kind=kind, fit=fit):
                                    index = 0
                                    if kind in {"video", "gif"}:
                                        index = min(1, int(at + .5)) if col == 1 else int(at + .5) % 2
                                    expected = reference(images[index], fit)
                                    # Sample flat interiors on both axes, clear of one-pixel filtered edges.
                                    for x in (4, 8, 23, 40, 43):
                                        for y in (3, 17, 23, 30, 45):
                                            actual = raster.getpixel((x + 48*col, y + 48*row))
                                            expected_color = expected.getpixel((x, y))
                                            self.assertLessEqual(max(abs(a-b) for a,b in zip(actual, expected_color)), 9,
                                                f"sample {(x, y)} expected {expected_color}, decoded {actual}")
                finally:
                    browser.close()


if __name__ == "__main__":
    unittest.main()
