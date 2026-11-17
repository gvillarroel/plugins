#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "fonttools>=4.55,<5", "playwright>=1.52,<2",
#   "python-pptx>=1.0.2,<2", "shapely>=2.1,<3",
# ]
# ///

from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
from pathlib import Path

# The skill bundle can be mounted read-only.
sys.dont_write_bytecode = True

from capture_svg import capture
from slides_batch import build_batch


def viewport_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value, re.IGNORECASE)
    if not match or any(not 100 <= int(axis) <= 4096 for axis in match.groups()):
        raise argparse.ArgumentTypeError("Use WIDTHxHEIGHT with each axis between 100 and 4096.")
    return int(match[1]), int(match[2])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a settled D3 SVG visual for native Google Slides."
    )
    parser.add_argument("source", type=Path, help="Trusted local SVG or HTML containing an SVG.")
    parser.add_argument("--selector", help="CSS selector for exactly one SVG root.")
    parser.add_argument("--viewport", type=viewport_size, default=(1280, 720))
    parser.add_argument("--wait-ms", type=int, default=0, help="Wait after the page and SVG load.")
    parser.add_argument("--frame-seconds", type=float,
                        help="Sample SVG and CSS animation at this time in seconds.")
    parser.add_argument("--system-fonts", action="store_true",
                        help="Block decorative Google Fonts and use installed fonts.")
    parser.add_argument("--device-scale", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--browser", choices=("auto", "chromium", "msedge", "chrome"), default="auto")
    parser.add_argument("--mode", choices=("auto", "editable", "image"), default="auto")
    parser.add_argument("--path-tolerance", type=float, default=0.45, metavar="PX",
                        help="Curve flattening tolerance in source CSS pixels. Default is 0.45.")
    parser.add_argument("--slide-id", required=True, help="Slide object ID from the deck, or a new ID with --create-slide.")
    parser.add_argument("--id-prefix", required=True, help="Unique visual object ID prefix within the deck.")
    parser.add_argument("--frame", nargs=4, type=float, required=True, metavar=("X", "Y", "W", "H"),
                        help="Top-left and size of the target frame in slide points.")
    parser.add_argument("--page-size", nargs=2, type=float, default=(720, 405), metavar=("W", "H"),
                        help="Page size in slide points. Default is 720 by 405.")
    parser.add_argument("--create-slide", action="store_true", help="Add a blank slide in the same batch.")
    parser.add_argument("--revision", help="Required revision ID from a fresh read of the target deck.")
    parser.add_argument("--alt-title", help="Override the SVG title used as image alt text.")
    parser.add_argument("--alt-description", help="Override the SVG description used as image alt text.")
    parser.add_argument("--preview", type=Path, required=True, help="Output source preview PNG.")
    parser.add_argument("--batch", type=Path, required=True, help="Output Slides batchUpdate JSON.")
    parser.add_argument("--report", type=Path, required=True, help="Output mode and placement report JSON.")
    parser.add_argument("--pptx", type=Path, help="Optional one-slide image snapshot for private Drive import.")
    return parser.parse_args()


def snapshot_pptx(
    png: bytes, frame: tuple[float, float, float, float], page_size: tuple[float, float],
    alt_title: str, alt_description: str,
) -> bytes:
    from pptx import Presentation
    from pptx.util import Pt

    presentation = Presentation()
    presentation.slide_width, presentation.slide_height = map(Pt, page_size)
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    picture = slide.shapes.add_picture(io.BytesIO(png), *map(Pt, frame))
    properties = picture._element.nvPicPr.cNvPr
    if alt_title:
        properties.set("title", alt_title)
    if alt_description:
        properties.set("descr", alt_description)
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode("utf-8")


def prepare(args: argparse.Namespace) -> dict:
    source = args.source.resolve()
    outputs = [args.preview.resolve(), args.batch.resolve(), args.report.resolve()]
    if args.pptx:
        outputs.append(args.pptx.resolve())
    if len({source, *outputs}) != len(outputs) + 1:
        raise ValueError("The source and every output must use distinct paths.")
    x, y, width, height = args.frame
    page_width, page_height = args.page_size
    if not all(math.isfinite(v) for v in (*args.frame, *args.page_size)):
        raise ValueError("Frame and page dimensions must be finite.")
    if x < 0 or y < 0 or width <= 0 or height <= 0:
        raise ValueError("Frame origins must be nonnegative and sizes must be positive.")
    if x + width > page_width + 1e-8 or y + height > page_height + 1e-8:
        raise ValueError("The target frame must fit the slide page.")
    if not 0 <= args.wait_ms <= 60_000:
        raise ValueError("The wait must be between 0 and 60000 milliseconds.")
    if not 0.1 <= args.path_tolerance <= 4:
        raise ValueError("The path tolerance must be between 0.1 and 4 CSS pixels.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_:-]{0,49}", args.slide_id):
        raise ValueError("Use a valid Google Slides slide object ID.")
    if args.create_slide and len(args.slide_id) < 5:
        raise ValueError("A new slide object ID must have at least 5 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_:-]{2,37}", args.id_prefix):
        raise ValueError("Use a 3 to 38 character visual object ID prefix.")

    preview, scene = capture(
        source, args.selector, args.viewport, args.wait_ms,
        args.device_scale, args.mode != "image", args.browser,
        frame_seconds=args.frame_seconds, allow_decorative_fonts=args.system_fonts,
    )
    unsupported = scene["unsupported"]
    if args.mode != "image" and not scene["marks"] and not unsupported:
        unsupported = ["The SVG contains no supported visible marks."]
    if args.mode == "editable" and unsupported:
        raise ValueError("Editable conversion refused. " + " ".join(unsupported))
    mode = "image" if args.mode == "image" or unsupported else "editable"
    title = scene["title"] if args.alt_title is None else args.alt_title
    description = scene["description"] if args.alt_description is None else args.alt_description
    batch_args = (args.slide_id, args.id_prefix, tuple(args.frame), outputs[0],
                  title, description, args.revision, args.create_slide, args.path_tolerance)
    try:
        batch, object_ids, fitted = build_batch(scene, mode, *batch_args)
    except ValueError as error:
        if args.mode != "auto" or mode != "editable":
            raise
        unsupported = [str(error)]
        mode = "image"
        batch, object_ids, fitted = build_batch(scene, mode, *batch_args)
    image_output = mode == "image" or args.pptx
    if image_output and not (title.strip() or description.strip()):
        raise ValueError("Supply SVG title or description, or pass meaningful image alt text.")
    if image_output and len(preview) >= 50_000_000:
        raise ValueError("The PNG exceeds the Slides image limit. Reduce --device-scale.")

    if args.slide_id in object_ids:
        raise ValueError("The visual object ID prefix collides with the target slide ID.")
    report = {
        "mode": mode,
        "slideId": args.slide_id,
        "objectIds": object_ids,
        "sourceSizePx": [scene["width"], scene["height"]],
        "pageSizePt": list(args.page_size),
        "framePt": list(fitted),
        "unsupported": unsupported,
        "preview": args.preview.name,
    }
    triangles = sum(item.get("createShape", {}).get("shapeType") == "RIGHT_TRIANGLE"
                    for item in batch["requests"])
    if triangles:
        report["pathGeometry"] = {"tolerancePx": args.path_tolerance, "nativeTriangles": triangles}
    if args.frame_seconds is not None:
        report["frameSeconds"] = args.frame_seconds
    if scene.get("blockedFonts"):
        report["blockedDecorativeFonts"] = scene["blockedFonts"]
    payloads = [preview, json_bytes(batch), json_bytes(report)]
    if args.pptx:
        payloads.append(snapshot_pptx(preview, fitted, tuple(args.page_size), title, description))
    for path, data in zip(outputs, payloads, strict=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return report


def main() -> int:
    args = parse_args()
    try:
        report = prepare(args)
    except (ValueError, OSError) as error:
        print(f"Transfer preparation failed. {error}", file=sys.stderr)
        return 1
    print(f"Prepared {report['mode']} transfer with {len(report['objectIds'])} visual objects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
