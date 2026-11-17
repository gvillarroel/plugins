#!/usr/bin/env python3
"""Render simple Printify-sized PNG assets and previews from local specs."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageFont


DEFAULT_SPEC = Path(__file__).resolve().parents[1] / "references" / "product-specs.json"


def parse_color(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        raise argparse.ArgumentTypeError(f"Expected #RRGGBB color, got {value!r}")
    return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def product_and_placement(spec: dict[str, Any], product_key: str, placement_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    products = spec.get("products", {})
    if product_key not in products:
        available = ", ".join(sorted(products))
        raise SystemExit(f"Unknown product key {product_key!r}. Available: {available}")

    product = products[product_key]
    placements = product.get("placements", {})
    if placement_key not in placements:
        available = ", ".join(sorted(placements))
        raise SystemExit(f"Unknown placement {placement_key!r} for {product_key}. Available: {available}")

    return product, placements[placement_key]


def font(size: int, bold: bool = False, monospace: bool = False) -> ImageFont.ImageFont:
    if monospace:
        candidates = [
            Path("C:/Windows/Fonts/consolab.ttf" if bold else "C:/Windows/Fonts/consola.ttf"),
            Path("C:/Windows/Fonts/courbd.ttf" if bold else "C:/Windows/Fonts/cour.ttf"),
        ]
    else:
        candidates = [
            Path("C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"),
        ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def centered_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, typeface: ImageFont.ImageFont, fill: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=typeface)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = left + (right - left - text_width) / 2
    y = top + (bottom - top - text_height) / 2 - bbox[1]
    draw.text((x, y), text, font=typeface, fill=fill)


def chroma_text(layer: Image.Image, position: tuple[int, int], text: str, typeface: ImageFont.ImageFont, anchor: str = "mm") -> None:
    draw = ImageDraw.Draw(layer)
    offsets = [
        ((-5, 0), (93, 219, 255, 132)),
        ((5, 0), (255, 83, 166, 124)),
        ((0, 0), (255, 250, 255, 246)),
    ]
    for (dx, dy), fill in offsets:
        draw.text((position[0] + dx, position[1] + dy), text, font=typeface, anchor=anchor, fill=fill)


def render_terminal(canvas: Image.Image, text: str, subtitle: str) -> None:
    width, height = canvas.size
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    origin_x = int(width * 0.57)
    origin_y = int(height * 0.33)
    cell = max(32, int(width * 0.025))
    wave = cell * 4
    gap = cell * 4
    max_radius = int(min(width, height) * 0.45)
    dark = (39, 13, 70, 104)
    dark_peak = (35, 10, 64, 150)

    for y in range(int(origin_y - max_radius), int(origin_y + max_radius), cell):
        for x in range(int(origin_x - max_radius), int(origin_x + max_radius), cell):
            distance = math.hypot(x + cell / 2 - origin_x, y + cell / 2 - origin_y)
            if distance > max_radius:
                continue
            phase = distance % (wave + gap)
            if phase > wave:
                continue
            alpha_factor = 1.0 - abs(phase - wave / 2) / (wave / 2)
            color = dark_peak if alpha_factor > 0.55 else dark
            draw.rectangle((x, y, x + cell, y + cell), fill=color)

    line_y = origin_y - int(height * 0.03)
    draw.line((int(width * 0.12), line_y, int(width * 0.92), line_y), fill=(255, 245, 255, 184), width=max(8, width // 260))

    tick_font = font(max(28, width // 80), monospace=True)
    tick_labels = ["low", "medium", "high", "xhigh", "max"]
    tick_start = int(width * 0.13)
    tick_gap = int(width * 0.105)
    for index, label in enumerate(tick_labels):
        x = tick_start + index * tick_gap
        draw.line((x, line_y - width // 180, x, line_y + width // 180), fill=(255, 245, 255, 110), width=max(3, width // 700))
        chroma_text(layer, (x, line_y + int(width * 0.023)), label, tick_font)

    draw.text((tick_start, line_y - int(width * 0.052)), "Faster", font=tick_font, fill=(255, 250, 255, 185), anchor="ls")
    draw.text((origin_x + int(width * 0.04), line_y - int(width * 0.02)), "Smarter", font=font(max(38, width // 60), monospace=True), fill=(255, 250, 255, 228), anchor="ls")

    label_font = font(max(72, width // 36), monospace=True)
    label_bbox = draw.textbbox((0, 0), text, font=label_font)
    label_width = label_bbox[2] - label_bbox[0]
    label_height = label_bbox[3] - label_bbox[1]
    label_x = origin_x
    label_y = line_y + int(height * 0.07)
    padding_x = int(width * 0.025)
    padding_y = int(width * 0.012)
    tag_box = (
        int(label_x - label_width / 2 - padding_x),
        int(label_y - label_height / 2 - padding_y),
        int(label_x + label_width / 2 + padding_x),
        int(label_y + label_height / 2 + padding_y),
    )
    draw.rectangle(tag_box, fill=(139, 79, 235, 218))
    chroma_text(layer, (label_x, label_y), text, label_font)

    triangle_top = line_y - int(width * 0.014)
    triangle_half = int(width * 0.014)
    draw.polygon(
        [
            (label_x, triangle_top),
            (label_x - triangle_half, tag_box[1]),
            (label_x + triangle_half, tag_box[1]),
        ],
        fill=(255, 250, 255, 246),
    )

    bottom_font = font(max(58, width // 44), monospace=True)
    chroma_text(layer, (label_x, tag_box[3] + int(height * 0.035)), subtitle, bottom_font)

    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.25)))


def render_badge(canvas: Image.Image, text: str, subtitle: str) -> None:
    width, height = canvas.size
    draw = ImageDraw.Draw(canvas)
    accent = (94, 61, 209, 235)
    ink = (255, 255, 255, 246)
    shadow = (40, 28, 70, 92)
    box_w = int(width * 0.70)
    box_h = int(height * 0.24)
    box = ((width - box_w) // 2, int(height * 0.24), (width + box_w) // 2, int(height * 0.24) + box_h)
    draw.rounded_rectangle((box[0] + 24, box[1] + 30, box[2] + 24, box[3] + 30), radius=32, fill=shadow)
    draw.rounded_rectangle(box, radius=32, fill=accent)
    centered_text(draw, (box[0], box[1] + int(box_h * 0.18), box[2], box[1] + int(box_h * 0.62)), text, font(max(72, width // 24), bold=True), ink)
    if subtitle:
        centered_text(draw, (box[0], box[1] + int(box_h * 0.60), box[2], box[3] - int(box_h * 0.10)), subtitle, font(max(40, width // 55)), (242, 238, 255, 220))


def render_children_marker(canvas: Image.Image, text: str, subtitle: str) -> None:
    width, height = canvas.size
    draw = ImageDraw.Draw(canvas)
    colors = [(238, 82, 83, 230), (72, 219, 251, 230), (29, 209, 161, 230), (254, 202, 87, 230)]
    center = (width // 2, int(height * 0.36))
    radius = min(width, height) * 0.18
    for index, color in enumerate(colors):
        angle = index * math.tau / len(colors) - math.pi / 4
        x = center[0] + int(math.cos(angle) * radius)
        y = center[1] + int(math.sin(angle) * radius)
        draw.line((center[0], center[1], x, y), fill=color, width=max(20, width // 90))
        draw.ellipse((x - width // 45, y - width // 45, x + width // 45, y + width // 45), fill=color)
    centered_text(draw, (int(width * 0.15), int(height * 0.43), int(width * 0.85), int(height * 0.55)), text, font(max(80, width // 22), bold=True), (45, 31, 68, 245))
    if subtitle:
        centered_text(draw, (int(width * 0.20), int(height * 0.55), int(width * 0.80), int(height * 0.62)), subtitle, font(max(42, width // 52)), (45, 31, 68, 210))


def render_mug_wrap(canvas: Image.Image, text: str, subtitle: str) -> None:
    width, height = canvas.size
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, width, height), fill=(255, 255, 255, 255))
    band_h = int(height * 0.18)
    draw.rectangle((0, int(height * 0.20), width, int(height * 0.20) + band_h), fill=(105, 73, 190, 255))
    draw.rectangle((0, int(height * 0.20) + band_h, width, int(height * 0.20) + band_h + int(height * 0.055)), fill=(45, 30, 80, 255))
    draw.rectangle((0, int(height * 0.62), width, int(height * 0.62) + int(height * 0.03)), fill=(105, 73, 190, 255))
    centered_text(draw, (int(width * 0.08), int(height * 0.23), int(width * 0.92), int(height * 0.36)), text, font(max(110, width // 18), bold=True), (255, 255, 255, 255))
    if subtitle:
        centered_text(draw, (int(width * 0.12), int(height * 0.405), int(width * 0.88), int(height * 0.49)), subtitle, font(max(62, width // 42)), (45, 30, 80, 245))
    small = font(max(36, width // 70), monospace=True)
    for x in (int(width * 0.18), int(width * 0.82)):
        draw.text((x, int(height * 0.68)), "front", font=small, fill=(105, 73, 190, 135), anchor="mm")


def create_canvas(width: int, height: int, transparent: bool, background: tuple[int, int, int]) -> Image.Image:
    if transparent:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))
    return Image.new("RGBA", (width, height), (*background, 255))


def save_preview(image: Image.Image, preview_path: Path, background: tuple[int, int, int], preview_width: int) -> None:
    preview = Image.new("RGBA", image.size, (*background, 255))
    preview.alpha_composite(image)
    if preview_width > 0 and preview.size[0] > preview_width:
        ratio = preview_width / preview.size[0]
        preview = preview.resize((preview_width, int(preview.size[1] * ratio)), Image.Resampling.LANCZOS)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_path, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--product-key", required=True)
    parser.add_argument("--placement", required=True)
    parser.add_argument("--style", choices=["terminal", "badge", "children-marker", "mug-wrap"], default="badge")
    parser.add_argument("--text", default="ultracost")
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--background", type=parse_color)
    parser.add_argument("--preview-width", type=int, default=1200)
    transparency = parser.add_mutually_exclusive_group()
    transparency.add_argument("--transparent", action="store_true")
    transparency.add_argument("--opaque", action="store_true")
    args = parser.parse_args()

    spec = load_json(args.spec)
    _, placement = product_and_placement(spec, args.product_key, args.placement)
    canvas_spec = placement["recommended_canvas"]
    width = args.width or int(canvas_spec["width"])
    height = args.height or int(canvas_spec["height"])
    background = args.background or parse_color(placement.get("preview_background", "#ffffff"))

    if args.transparent:
        transparent = True
    elif args.opaque:
        transparent = False
    else:
        transparent = bool(placement.get("default_transparent", True))

    canvas = create_canvas(width, height, transparent, background)

    if args.style == "terminal":
        render_terminal(canvas, args.text, args.subtitle)
    elif args.style == "children-marker":
        render_children_marker(canvas, args.text, args.subtitle)
    elif args.style == "mug-wrap":
        render_mug_wrap(canvas, args.text, args.subtitle)
    else:
        render_badge(canvas, args.text, args.subtitle)

    if not transparent:
        flattened = Image.new("RGBA", canvas.size, (*background, 255))
        flattened.alpha_composite(canvas)
        canvas = flattened

    args.output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.output, optimize=True)

    if args.preview:
        save_preview(canvas, args.preview, background, args.preview_width)

    print(json.dumps({"output": str(args.output), "size": [width, height], "transparent": transparent}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
