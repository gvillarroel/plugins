"""Build honest, scale-preserving review evidence; do not score design quality."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

REPO = Path.cwd().resolve()
KINDS = {"artwork", "schematic_product", "supplier_mockup", "physical_sample_photo", "campaign"}
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}\Z")


def local_path(path: Path) -> Path:
    path = path.resolve()
    if not path.is_relative_to(REPO):
        raise ValueError(f"Path must remain inside repository: {path}")
    return path


def relative(path: Path) -> str:
    return local_path(path).relative_to(REPO).as_posix()


def box_valid(box, limit, name):
    if not isinstance(box, list) or len(box) != 4 or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in box
    ):
        raise ValueError(f"{name}: expected four finite numeric coordinates")
    x0, y0, x1, y1 = box
    a, b, c, d = limit
    if not (a <= x0 < x1 <= c and b <= y0 < y1 <= d):
        raise ValueError(f"{name}: invalid bounds or outside view")
    return box


def wrapped(draw, xy, value, font, width, fill="#e9e5db"):
    x, y = xy
    line = ""
    for word in value.split():
        trial = f"{line} {word}".strip()
        if line and draw.textlength(trial, font=font) > width:
            draw.text((x, y), line, font=font, fill=fill)
            y += 23
            line = word
        else:
            line = trial
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += 23
    return y


def build(manifest_path: Path, out_dir: Path, report_path: Path):
    manifest_path, out_dir, report_path = map(local_path, (manifest_path, out_dir, report_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    widths = manifest.get("widths", [300, 600])
    if (not isinstance(widths, list) or not 1 <= len(widths) <= 2 or
            any(type(w) is not int or not 100 <= w <= 1200 for w in widths) or len(set(widths)) != len(widths)):
        raise ValueError("widths: use one or two distinct integer widths in 100..1200")
    threshold = manifest.get("small_text_risk_px", 8)
    if type(threshold) not in (float, int) or not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("small_text_risk_px must be a finite positive number")
    items = manifest.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("items must be a nonempty list")
    font_path = manifest.get("font_path")
    font = ImageFont.truetype(font_path, 17) if font_path else ImageFont.load_default(size=17)
    title_font = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default(size=24)
    seen, sources, groups, rows = set(), set(), {}, []
    for item in items:
        key, group = item.get("id", ""), item.get("group", "")
        if not SLUG.fullmatch(key) or not SLUG.fullmatch(group) or key in seen:
            raise ValueError("Unique IDs and group names must be filename-safe slugs")
        seen.add(key)
        kind, provenance = item.get("kind"), item.get("provenance", "")
        if kind not in KINDS or not isinstance(provenance, str) or not provenance.strip():
            raise ValueError(f"{key}: supply a recognized kind and explicit provenance")
        source = local_path(manifest_path.parent / item["image"])
        sources.add(source)
        with Image.open(source) as original:
            source_size = original.size
            rgba = original.convert("RGBA")
        if rgba.getchannel("A").getbbox() is None:
            raise ValueError(f"{key}: image is completely transparent")
        crop = item.get("crop", [0, 0, *source_size])
        box_valid(crop, [0, 0, *source_size], f"{key} crop")
        if any(type(v) is not int for v in crop):
            raise ValueError(f"{key}: crop coordinates must be integers")
        crop_note = item.get("crop_note", "")
        if "crop" in item and (not isinstance(crop_note, str) or not crop_note.strip()):
            raise ValueError(f"{key}: an explicit crop requires crop_note")
        rgba = rgba.crop(crop)
        background = item.get("background", "#121415")
        base = Image.new("RGBA", rgba.size, (*ImageColor.getrgb(background), 255))
        rgb = Image.alpha_composite(base, rgba).convert("RGB")
        regions = item.get("regions", [])
        for region in regions:
            if not isinstance(region.get("label"), str) or not region["label"].strip():
                raise ValueError(f"{key}: every region needs a label")
            box_valid(region["box"], crop, f"{key} region")
        views = []
        thumbnails = []
        for width in widths:
            height = max(1, round(rgb.height * width / rgb.width))
            if height > 3600:
                raise ValueError(f"{key}: view too tall for a review board; supply a meaningful framed image")
            thumb = rgb.resize((width, height), Image.Resampling.LANCZOS)
            projected = []
            for region in regions:
                b = region["box"]
                h = (b[3] - b[1]) * height / rgb.height
                projected.append({"label": region["label"], "source_box": b,
                                  "projected_box_height_px": round(h, 2),
                                  "small_text_review_warning": h < threshold})
            views.append({"width_px": width, "height_px": height, "regions": projected})
            thumbnails.append(thumb)
        row = {"id": key, "group": group, "kind": kind, "provenance": provenance,
               "source": relative(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
               "source_size": list(source_size), "view_box": crop,
               "crop_note": crop_note or "Uncropped source; no automatic trimming",
               "background": background, "views": views}
        rows.append(row)
        groups.setdefault(group, []).append((row, thumbnails))
    outputs = {local_path(out_dir / f"{group}.png") for group in groups} | {report_path}
    if len(outputs) != len(groups) + 1 or outputs & (sources | {manifest_path}):
        raise ValueError("Outputs must not overwrite source images, manifest, or each other")
    out_dir.mkdir(parents=True, exist_ok=True)
    boards = []
    for group, entries in groups.items():
        board_width = max(720, sum(widths) + 24 * (len(widths) + 1))
        layout = []
        # Calculate metadata heights with the same wrapping function used to draw them.
        probe = ImageDraw.Draw(Image.new("RGB", (board_width, 1)))
        title = f"{manifest.get('title', 'Design review')} / {group}"
        title_end = wrapped(probe, (24, 18), title, title_font, board_width - 48)
        subtitle = "Inspect at 100% | Keep framing | Measurements are review hints"
        header_end = wrapped(probe, (24, title_end + 20), subtitle, font, board_width - 48)
        y = header_end + 30
        for row, thumbnails in entries:
            meta = f"{row['id']} | {row['kind']} | {row['provenance']}"
            details = row["crop_note"]
            end = wrapped(probe, (24, y), meta, font, board_width - 48)
            end = wrapped(probe, (24, end), details, font, board_width - 48)
            img_y = end + 30
            after_images = img_y + max(i.height for i in thumbnails)
            layout.append((y, img_y, row, thumbnails))
            y = after_images + 26
        footer = "Evidence board. No aesthetic, physical-quality or sales verdict is automated."
        footer_end = wrapped(probe, (24, y + 10), footer, font, board_width - 48)
        board = Image.new("RGB", (board_width, footer_end + 24), "#282b30")
        draw = ImageDraw.Draw(board)
        wrapped(draw, (24, 18), title, title_font, board_width - 48)
        wrapped(draw, (24, title_end + 20), subtitle, font, board_width - 48, fill="#b5bac2")
        for top, img_y, row, thumbnails in layout:
            end = wrapped(draw, (24, top), f"{row['id']} | {row['kind']} | {row['provenance']}", font, board_width - 48)
            wrapped(draw, (24, end), row["crop_note"], font, board_width - 48, fill="#b5bac2")
            x = 24
            for width, thumb in zip(widths, thumbnails):
                draw.text((x, img_y - 26), f"{width} px wide", font=font, fill="#e9e5db")
                board.paste(thumb, (x, img_y))
                x += width + 24
        wrapped(draw, (24, y + 10), footer, font, board_width - 48, fill="#b5bac2")
        target = local_path(out_dir / f"{group}.png")
        board.save(target)
        boards.append({"group": group, "image": relative(target), "size": list(board.size),
                       "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    report = {"schema_version": 1, "manifest": relative(manifest_path),
              "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
              "widths": widths, "small_text_risk_px": threshold,
              "limitations": ["Provenance is declared, not authenticated by this script.",
                              "Region height is a bounding-box projection, not OCR or a legibility test.",
                              "No automated aesthetic, product acceptance, or sales judgment."],
              "items": rows, "boards": boards}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build(args.manifest, args.out_dir, args.report)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Review evidence error: {exc}\n")
    print(json.dumps({"items": len(report["items"]), "boards": len(report["boards"]), "report": relative(args.report)}))


if __name__ == "__main__":
    main()
