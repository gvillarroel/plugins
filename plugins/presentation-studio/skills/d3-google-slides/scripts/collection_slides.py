#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools>=4.55,<5", "playwright>=1.52,<2", "Pillow>=10,<13",
#   "python-pptx>=1.0.2,<2", "shapely>=2.1,<3",
# ]
# ///
"""Transfer every visual in a local collection to a checked Slides handoff."""

from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby
from pathlib import Path
from urllib.parse import urlsplit

sys.dont_write_bytecode = True

from PIL import Image, ImageChops, ImageFont
from playwright.sync_api import Error as PlaywrightError, sync_playwright
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt
from shapely.errors import GEOSException

from capture_svg import _launch_options, capture_locator, hide_controls, load_local_page
from editable_pptx import add_mark
from layered_capture import isolate_layers
from presentation_capture import crop_presentation, declared_frame


SLIDE_SIZE = (720, 405)
VISUAL_FRAME = (32, 54, 656, 310)
IDENTITY = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}")
RASTER_TYPES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@dataclass(frozen=True)
class Case:
    id: str
    source: Path | None
    selector: str | None
    title: str | None = None
    link: str | None = None
    time: float | None = None
    fragment: str | None = None
    select: dict[str, str] | None = None
    click: str | None = None
    wait_after_ms: int = 0


def authorized_link(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Original links must use HTTPS without embedded credentials.")
    return value


def manifest_cases(path: Path) -> list[Case]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for entry in data["cases"]:
        source = entry.get("source")
        cases.append(Case(
            entry["id"],
            (path.parent / source).resolve() if source else None,
            entry.get("selector"),
            entry.get("title"),
            authorized_link(entry.get("link")),
            entry.get("frameSeconds"),
            entry.get("fragment"),
            entry.get("select"),
            entry.get("click"),
            entry.get("waitAfterMs", 0),
        ))
    return cases


def frame_fit(width: float, height: float, available=VISUAL_FRAME) -> tuple[float, float, float]:
    left, top, available_width, available_height = available
    scale = min(available_width / width, available_height / height)
    return (left + (available_width - width * scale) / 2,
            top + (available_height - height * scale) / 2, scale)


@lru_cache(maxsize=1)
def heading_font():
    for filename in ("arialbd.ttf", "LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(filename, 100)
        except OSError:
            continue
    return ImageFont.load_default(size=100)


def heading_style(title):
    measure = heading_font().getlength
    one_line = min(24, 61_600 / max(1, measure(title)))
    words = title.split()
    if one_line >= 18 or len(words) < 2:
        return one_line, False
    balanced = min(max(measure(" ".join(words[:i])), measure(" ".join(words[i:])))
                   for i in range(1, len(words)))
    two_lines = min(20, 61_600 / max(1, balanced))
    return (two_lines, True) if two_lines > one_line else (one_line, False)


def paint_label(slide, text: str, box: tuple[float, float, float, float],
                size: float, *, link: str | None = None, bold: bool = False, wrap: bool = False) -> None:
    shape = slide.shapes.add_textbox(*map(Pt, box))
    frame = shape.text_frame
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = Pt(0)
    frame.word_wrap = wrap
    paragraph = frame.paragraphs[0]
    paragraph.alignment = PP_ALIGN.LEFT
    run = paragraph.add_run()
    run.text = text
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string("9E1B32" if link else "1C1C1C")
    if link:
        run.hyperlink.address = link


def check_picture(data: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        rgb = Image.new("RGB", image.size, "white")
        rgba = image.convert("RGBA")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        solid = Image.new("RGB", image.size, rgb.getpixel((0, 0)))
        if ImageChops.difference(rgb, solid).getbbox() is None:
            raise ValueError("The captured state has no visible content.")
        return image.size


def place_picture(slide, picture: bytes, frame: tuple[float, float, float, float],
                  title: str, description: str) -> None:
    embedded = slide.shapes.add_picture(io.BytesIO(picture), *map(Pt, frame))
    properties = embedded._element.nvPicPr.cNvPr
    properties.set("title", title)
    properties.set("descr", description)


def create_slide(deck, case: Case, scene: dict | None, picture: bytes | None, mode: str) -> dict:
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    title = case.title or (scene or {}).get("title") or case.id
    title = " ".join(title.split())
    title_size, wrap = heading_style(title)
    title_box = (32, 15, 656, 48) if wrap else (32, 22, 656, 28)
    available = (32, 70, 656, 294) if wrap else VISUAL_FRAME
    paint_label(slide, title, title_box, title_size, bold=True, wrap=wrap)
    initial = len(slide.shapes)
    reason = list((scene or {}).get("unsupported", []))
    approximations = set()
    representation = "reference" if picture is None else "image"
    raster_count = 0
    visual_frame = None
    layers = (scene or {}).get("layers")
    if scene and mode != "image" and (not reason or layers):
        width, height = scene["width"], scene["height"]
        fit = frame_fit(width, height, available)
        visual_frame = [fit[0], fit[1], width * fit[2], height * fit[2]]
        try:
            for layer in layers or [{"marks": scene["marks"]}]:
                if "marks" in layer:
                    for mark in layer["marks"]:
                        add_mark(slide.shapes, mark, fit, (width, height), approximations)
                else:
                    x, y, w, h = layer["frame"]
                    left, top, scale = fit
                    place_picture(slide, layer["png"],
                                  (left + x * scale, top + y * scale, w * scale, h * scale),
                                  title, f"Raster layer of {title}.")
                    raster_count += 1
        except (ValueError, GEOSException) as error:
            reason.append(str(error))
            for shape in list(slide.shapes)[initial:]:
                shape._element.getparent().remove(shape._element)
            approximations.clear()
            raster_count = 0
        if len(slide.shapes) - initial > raster_count:
            representation = "hybrid" if raster_count else "editable"
        elif raster_count:
            for shape in list(slide.shapes)[initial:]:
                shape._element.getparent().remove(shape._element)
            raster_count = 0
        elif not reason:
            reason.append("The selected state contains no editable geometry.")

    if representation == "image":
        if mode == "editable":
            raise ValueError(f"{case.id} needs a snapshot. {' '.join(reason)}")
        width, height = check_picture(picture)
        left, top, scale = frame_fit(width, height, available)
        visual_frame = [left, top, width * scale, height * scale]
        place_picture(slide, picture, (left, top, width * scale, height * scale), title,
                      (scene or {}).get("description") or f"Captured state of {title}.")
        raster_count = 1
    visual_objects = len(slide.shapes) - initial
    if case.link:
        paint_label(slide, "Open original", (550, 377, 138, 16), 11, link=case.link)
    paint_label(slide, case.id, (32, 377, 503, 16), 10)
    report = {
        "id": case.id, "title": title, "representation": representation,
        "visualObjects": visual_objects, "frameSeconds": case.time,
        "editableObjects": visual_objects - raster_count, "imageObjects": raster_count,
        "original": case.link, "unsupported": reason, "approximations": sorted(approximations),
    }
    if representation == "hybrid":
        report["hybridCheck"] = scene["hybridCheck"]
    if visual_frame:
        report["framePt"] = visual_frame
    if scene and "sourceCropPx" in scene:
        report["sourceCropPx"] = scene["sourceCropPx"]
    return report


def discover(page, source: Path, selector: str, base_url: str | None, time: float | None) -> list[Case]:
    locator = page.locator(selector)
    locator.first.wait_for(state="attached", timeout=20_000)
    entries = locator.evaluate_all(r"""nodes => nodes.map(node => {
        const owner = node.closest('[data-pattern-id], [data-example], [data-example-id]');
        const id = node.getAttribute('data-pattern-id') || owner?.getAttribute('data-pattern-id') ||
            owner?.getAttribute('data-example') || node.id || owner?.id;
        const title = node.querySelector(':scope > title')?.textContent ||
            owner?.querySelector('h2, h3')?.textContent || node.getAttribute('aria-label');
        return {id, title, anchor: owner?.id || node.id || null};
    })""")
    cases = []
    for index, entry in enumerate(entries):
        original = base_url
        if base_url and entry["anchor"]:
            original = base_url.split("#")[0] + "#" + entry["anchor"]
        cases.append(Case(entry["id"] or f"visual-{index + 1:04d}", source, None,
                          entry["title"], original, time))
    return cases


def check_cases(cases: list[Case], expected: int | None) -> None:
    if not cases or (expected is not None and len(cases) != expected):
        raise ValueError(f"Expected {expected or 'at least one'} case, found {len(cases)}.")
    ids = set()
    for case in cases:
        if not IDENTITY.fullmatch(case.id) or case.id in ids:
            raise ValueError(f"Invalid or duplicate case ID: {case.id!r}.")
        ids.add(case.id)
        if case.time is not None and (not math.isfinite(case.time) or not 0 <= case.time <= 60):
            raise ValueError(f"Invalid frame time for {case.id}.")
        if case.fragment and not IDENTITY.fullmatch(case.fragment):
            raise ValueError(f"Invalid fragment ID for {case.id}.")
        if not isinstance(case.wait_after_ms, int) or not 0 <= case.wait_after_ms <= 60_000:
            raise ValueError(f"Invalid post-action wait for {case.id}.")
        if case.source is None and not (case.title and case.link):
            raise ValueError(f"A reference case needs a title and link: {case.id}.")
        if case.source is not None and (not case.source.is_file() or
                                        case.source.suffix.lower() not in RASTER_TYPES | {".svg", ".html", ".htm"}):
            raise ValueError(f"Supply a trusted local SVG, HTML, or raster image for {case.id}.")


def capture_case(locator, case: Case, args) -> tuple[bytes, dict]:
    with hide_controls(locator, args.exclude):
        if locator.evaluate("element => element.localName") != "svg":
            if args.mode == "editable":
                raise ValueError(f"{case.id} is an HTML or canvas surface. Choose a snapshot or original link.")
            image = locator.screenshot(omit_background=True, timeout=20_000)
            return image, {"title": case.title, "unsupported": ["HTML or canvas surface."]}
        picture, scene = capture_locator(locator, device_scale=args.scale, editable=args.mode != "image",
                                         allow_gradients=True, frame_seconds=case.time,
                                         paint_units=args.mode == "auto", mark_limit=args.mark_limit)
        if args.mode == "auto" and scene["unsupported"]:
            layers, problem = isolate_layers(locator, scene, picture)
            if layers:
                scene["layers"] = layers
            if problem:
                scene["unsupported"].append(problem)
        return crop_presentation(picture, scene, declared_frame(locator), args.trim_padding, VISUAL_FRAME[2:])


def apply_case_controls(page, case: Case) -> None:
    if case.fragment:
        page.evaluate("fragment => { location.hash = fragment; }", case.fragment)
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(resolve))")
    for selector, value in (case.select or {}).items():
        control = page.locator(selector)
        if control.input_value() != value:
            control.select_option(value)
    if case.click:
        page.locator(case.click).click()
    if case.wait_after_ms:
        page.wait_for_timeout(case.wait_after_ms)


def raster_frame(case: Case) -> bytes:
    with Image.open(case.source) as source:
        if source.width * source.height > 25_000_000:
            raise ValueError(f"The raster visual exceeds 25 megapixels: {case.id}.")
        if case.time is not None and getattr(source, "is_animated", False):
            durations = []
            for index in range(source.n_frames):
                source.seek(index)
                durations.append(max(1, source.info.get("duration", 100)))
            time = case.time * 1000
            period = sum(durations)
            if source.info.get("loop") == 0:
                time %= period
            for index, duration in enumerate(durations):
                if time < duration or index == len(durations) - 1:
                    source.seek(index)
                    break
                time -= duration
        result = io.BytesIO()
        source.convert("RGBA").save(result, format="PNG")
        return result.getvalue()


def build_collection(args) -> dict:
    input_raster = args.source and args.source.suffix.lower() in RASTER_TYPES
    if args.source and not input_raster and not args.selector:
        raise ValueError("Set --selector when discovering visuals from --source.")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError("Use an empty output directory.")
    cases = manifest_cases(args.manifest) if args.manifest else None
    if input_raster:
        cases = [Case(args.name, args.source.resolve(), None, args.source.stem,
                      authorized_link(args.original_url), args.frame_seconds)]
    if cases is not None:
        check_cases(cases, args.expected)
    results, volumes, blocked_fonts = [], [], set()
    deck = None

    def append(case: Case, picture=None, scene=None):
        nonlocal deck
        if deck is None:
            deck = Presentation()
            deck.slide_width, deck.slide_height = map(Pt, SLIDE_SIZE)
        result = create_slide(deck, case, scene, picture, args.mode)
        result["deck"] = f"{args.name}-{len(volumes) + 1:02d}.pptx"
        result["slide"] = len(deck.slides)
        if args.previews and picture:
            previews = args.output_dir / "previews"
            previews.mkdir(parents=True, exist_ok=True)
            (previews / f"{case.id}.png").write_bytes(picture)
            result["preview"] = f"previews/{case.id}.png"
        results.append(result)
        if len(deck.slides) == args.volume_size:
            save()

    def save():
        nonlocal deck
        if deck is None:
            return
        name = f"{args.name}-{len(volumes) + 1:02d}.pptx"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        deck.save(args.output_dir / name)
        volumes.append({"file": name, "slides": len(deck.slides)})
        deck = None

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**_launch_options(playwright, args.browser))
        context = browser.new_context(viewport={"width": 1600, "height": 1000},
                                      device_scale_factor=args.scale, service_workers="block")
        if cases is None:
            source = args.source.resolve()
            page = context.new_page()
            guard = load_local_page(page, source, allow_decorative_fonts=args.system_fonts)
            cases = discover(page, source, args.selector, authorized_link(args.original_url), args.frame_seconds)
            check_cases(cases, args.expected)
            page.wait_for_timeout(args.wait_ms)
            locator = page.locator(args.selector)
            for index, case in enumerate(cases):
                picture, scene = capture_case(locator.nth(index), case, args)
                append(case, picture, scene)
            guard.check()
            blocked_fonts.update(guard.blocked_fonts)
            page.close()
        else:
            for source, group in groupby(cases, key=lambda case: case.source):
                if source is None:
                    for case in group:
                        append(case)
                    continue
                if source.suffix.lower() in RASTER_TYPES:
                    for case in group:
                        append(case, raster_frame(case), {"unsupported": ["Raster source."]})
                    continue
                page = context.new_page()
                guard = load_local_page(page, source, allow_decorative_fonts=args.system_fonts)
                page.wait_for_timeout(args.wait_ms)
                for case in group:
                    apply_case_controls(page, case)
                    locator = page.locator(case.selector or "svg")
                    locator.first.wait_for(state="attached", timeout=20_000)
                    if locator.count() != 1:
                        raise ValueError(f"Select exactly one visual for {case.id}.")
                    picture, scene = capture_case(locator, case, args)
                    append(case, picture, scene)
                guard.check()
                blocked_fonts.update(guard.blocked_fonts)
                page.close()
        context.close()
        browser.close()
    save()
    return {"schemaVersion": 1, "count": len(results), "volumes": volumes,
            "blockedDecorativeFonts": sorted(blocked_fonts), "items": results}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", type=Path, help="Trusted local gallery HTML or SVG.")
    source.add_argument("--manifest", type=Path, help="JSON file with a cases array.")
    parser.add_argument("--selector", help="CSS selector matching all visuals in --source.")
    parser.add_argument("--expected", type=int, help="Require this many visual or reference entries.")
    parser.add_argument("--mode", choices=("auto", "editable", "image"), default="auto")
    parser.add_argument("--name", default="d3-collection", help="Safe output deck basename.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--volume-size", type=int, default=40, choices=range(1, 101), metavar="N")
    parser.add_argument("--wait-ms", type=int, default=4500, help="Wait once for each HTML document.")
    parser.add_argument("--frame-seconds", type=float, help="SMIL/CSS frame time for --source.")
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--mark-limit", type=int, default=3000,
                        help="Maximum editable SVG marks per visual, from 1 through 6000.")
    parser.add_argument("--browser", choices=("auto", "chromium", "msedge", "chrome"), default="auto")
    parser.add_argument("--original-url", help="Authorized HTTPS URL of the interactive --source.")
    parser.add_argument("--previews", action="store_true", help="Save one source PNG per visual.")
    parser.add_argument("--exclude", action="append", default=[], metavar="SELECTOR",
                        help="Hide a presentation-only control without reflow. Repeat for multiple selectors.")
    parser.add_argument("--trim-padding", action="store_true",
                        help="Trim flat outer SVG padding when it materially improves scale without clipping paint.")
    parser.add_argument("--system-fonts", action="store_true",
                        help="Block decorative Google Fonts requests and use local fonts.")
    args = parser.parse_args()
    if not IDENTITY.fullmatch(args.name) or not 0 <= args.wait_ms <= 60_000 or not 1 <= args.mark_limit <= 6000:
        parser.error("Use a safe deck basename, a wait from 0 through 60000 ms, and a mark limit from 1 through 6000.")
    try:
        report = build_collection(args)
        (args.output_dir / "coverage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    except (ValueError, OSError, KeyError, TypeError, PlaywrightError) as error:
        print(f"Collection transfer failed. {error}", file=sys.stderr)
        return 1
    print(f"Prepared {report['count']} cases in {len(report['volumes'])} volumes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
