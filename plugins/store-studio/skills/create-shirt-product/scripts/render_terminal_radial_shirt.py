#!/usr/bin/env python3
"""Render a transparent, print-ready terminal/radial shirt design."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


REF_W = 1080
REF_H = 163


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB color, got {value!r}")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def dark_pulse_opacity(
    x: float,
    y: float,
    origin_x: float,
    origin_y: float,
    square_cell: int,
    wave_cells: float,
    gap_cells: float,
) -> float:
    cycle = wave_cells + gap_cells
    distance_cells = math.hypot(x - origin_x, y - origin_y) / square_cell
    phase_cells = distance_cells % cycle
    if phase_cells >= wave_cells:
        return 0.0

    center = wave_cells / 2
    edge = abs(phase_cells - center) / center
    return 0.26 + (1.0 - edge) * 0.30


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("C:/Windows/Fonts/cour.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def text_layer(
    size: tuple[int, int],
    text: str,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
    anchor: str = "mm",
) -> Image.Image:
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    offsets = [
        ((-3, 0), (70, 217, 255, 130)),
        ((3, 0), (255, 75, 160, 115)),
        ((0, 0), (255, 248, 255, 245)),
    ]
    for (dx, dy), fill in offsets:
        draw.text((x + dx, y + dy), text, font=font, anchor=anchor, fill=fill)
    return layer.filter(ImageFilter.GaussianBlur(0.35))


def render_design(
    output: Path,
    width: int,
    height: int,
    label: str,
    bottom: str,
    mode: str,
    radius_ref: float,
    square_cell_ref: float,
    draw_cell_ref: float,
    y_frac: float,
    base_preview: str,
    preview: Path | None,
) -> None:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    scale = min(width * 0.86 / REF_W, height * 0.22 / REF_H)
    design_w = int(REF_W * scale)
    ox = (width - design_w) // 2
    oy = int(height * y_frac)

    def sx(value: float) -> int:
        return int(ox + value * scale)

    def sy(value: float) -> int:
        return int(oy + value * scale)

    def ss(value: float) -> int:
        return max(1, int(value * scale))

    origin_x = sx(760)
    origin_y = sy(96)
    max_radius = ss(radius_ref)
    cell_w = ss(draw_cell_ref)
    cell_h = ss(draw_cell_ref)
    square_cell = ss(square_cell_ref)

    blocks = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blocks)
    if mode == "fill":
        loop_x0, loop_y0 = -cell_w, -cell_h
        loop_x1, loop_y1 = width + cell_w, height + cell_h
    else:
        loop_x0 = origin_x - max_radius - cell_w
        loop_y0 = origin_y - max_radius - cell_h
        loop_x1 = origin_x + max_radius + cell_w
        loop_y1 = origin_y + max_radius + cell_h

    for y in range(loop_y0, loop_y1, cell_h):
        for x in range(loop_x0, loop_x1, cell_w):
            cx = x + cell_w / 2
            cy = y + cell_h / 2
            if mode == "clean":
                farthest_corner = max(
                    math.hypot(px - origin_x, py - origin_y)
                    for px, py in (
                        (x, y),
                        (x + cell_w, y),
                        (x, y + cell_h),
                        (x + cell_w, y + cell_h),
                    )
                )
                if farthest_corner > max_radius:
                    continue

            opacity = dark_pulse_opacity(
                cx,
                cy,
                origin_x,
                origin_y,
                square_cell,
                wave_cells=4.0,
                gap_cells=4.0,
            )
            if opacity > 0:
                bd.rectangle(
                    (x, y, x + cell_w + ss(2), y + cell_h + ss(2)),
                    fill=(*hex_to_rgb("#17062f"), int(opacity * 245)),
                )
    img = Image.alpha_composite(img, blocks.filter(ImageFilter.GaussianBlur(ss(0.45))))

    title_font = load_font(ss(18))
    option_font = load_font(ss(17))
    small_font = load_font(ss(16))
    label_font = load_font(ss(20))
    bottom_font = load_font(ss(18))

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    line_y = sy(75)
    line_x0 = sx(248)
    line_x1 = sx(838)
    od.rectangle((line_x0, line_y - ss(1.5), line_x1, line_y + ss(1.5)), fill=(234, 217, 255, 178))
    od.rectangle((line_x0, line_y - ss(0.5), line_x1, line_y + ss(0.5)), fill=(255, 255, 255, 94))

    tick_data = [
        ("low", 263),
        ("medium", 354),
        ("high", 447),
        ("xhigh", 535),
        ("max", 630),
    ]
    for _name, x_ref in tick_data:
        tx = sx(x_ref)
        od.rectangle((tx - ss(0.8), line_y - ss(8), tx + ss(0.8), line_y + ss(8)), fill=(234, 217, 255, 122))

    img = Image.alpha_composite(img, text_layer((width, height), "Effort", sx(28), sy(16), title_font, anchor="ls"))
    img = Image.alpha_composite(img, text_layer((width, height), "Faster", sx(277), sy(58), option_font, anchor="mm"))
    img = Image.alpha_composite(img, text_layer((width, height), "Smarter", sx(805), sy(58), option_font, anchor="mm"))
    for name, x_ref in tick_data:
        img = Image.alpha_composite(img, text_layer((width, height), name, sx(x_ref), sy(101), small_font, anchor="mm"))

    marker_x = sx(758)
    marker_w = ss(28)
    marker_h = ss(42)
    label_x = sx(713)
    label_y = sy(86)
    label_w = ss(101)
    label_h = ss(25)
    od.rectangle(
        (marker_x - marker_w // 2, line_y - marker_h // 2, marker_x + marker_w // 2, line_y + marker_h // 2),
        fill=(141, 76, 241, 238),
    )
    od.polygon(
        [
            (marker_x, line_y - ss(9)),
            (marker_x - ss(8), line_y + ss(8)),
            (marker_x + ss(8), line_y + ss(8)),
        ],
        fill=(255, 248, 255, 252),
    )
    od.rectangle((label_x, label_y, label_x + label_w, label_y + label_h), fill=(141, 76, 241, 245))
    od.rectangle((label_x, label_y, label_x + label_w, label_y + ss(2)), fill=(179, 131, 255, 145))
    img = Image.alpha_composite(img, overlay)

    img = Image.alpha_composite(
        img,
        text_layer((width, height), label, label_x + label_w // 2, label_y + ss(19), label_font, anchor="mm"),
    )
    img = Image.alpha_composite(
        img,
        text_layer((width, height), bottom, sx(676), sy(128), bottom_font, anchor="ls"),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    img.save(output)

    if preview:
        canvas = Image.new("RGBA", img.size, (*hex_to_rgb(base_preview), 255))
        canvas.alpha_composite(img)
        canvas.thumbnail((1000, 1200), Image.Resampling.LANCZOS)
        preview.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(preview, quality=94)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--width", type=int, default=4500)
    parser.add_argument("--height", type=int, default=5400)
    parser.add_argument("--label", default="ultracost")
    parser.add_argument("--bottom", default="xhigh + workflows")
    parser.add_argument("--mode", choices=["clean", "fill"], default="clean")
    parser.add_argument("--radius-ref", type=float, default=350)
    parser.add_argument("--square-cell-ref", type=float, default=12.5)
    parser.add_argument("--draw-cell-ref", type=float, default=6)
    parser.add_argument("--y-frac", type=float, default=0.31)
    parser.add_argument("--base-preview", default="#a682db")
    args = parser.parse_args()

    if args.output.suffix.lower() != ".png":
        raise SystemExit("Output must be a .png file.")
    render_design(
        output=args.output,
        width=args.width,
        height=args.height,
        label=args.label,
        bottom=args.bottom,
        mode=args.mode,
        radius_ref=args.radius_ref,
        square_cell_ref=args.square_cell_ref,
        draw_cell_ref=args.draw_cell_ref,
        y_frac=args.y_frac,
        base_preview=args.base_preview,
        preview=args.preview,
    )
    print(f"Generated {args.output.resolve()}")
    if args.preview:
        print(f"Generated {args.preview.resolve()}")


if __name__ == "__main__":
    main()
