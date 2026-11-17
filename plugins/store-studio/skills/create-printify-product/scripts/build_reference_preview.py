#!/usr/bin/env python3
"""Build an approximate product preview over a saved Printify reference image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path.cwd().resolve()
DEFAULT_TEMPLATES = SKILL_DIR / "references" / "preview-templates.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def parse_box(value: str) -> tuple[float, float, float, float]:
    parts = [float(part.strip()) for part in value.split(",") if part.strip()]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("Expected box as x,y,width,height")
    if any(part < 0 for part in parts) or parts[0] + parts[2] > 1 or parts[1] + parts[3] > 1:
        raise argparse.ArgumentTypeError("Box values must be normalized and stay inside 0..1")
    return tuple(parts)  # type: ignore[return-value]


def fit_image(art: Image.Image, box_size: tuple[int, int], fit: str) -> Image.Image:
    box_w, box_h = box_size
    if art.width == 0 or art.height == 0:
        raise ValueError("Art image has invalid dimensions")
    if fit == "cover":
        scale = max(box_w / art.width, box_h / art.height)
    else:
        scale = min(box_w / art.width, box_h / art.height)
    new_size = (max(1, int(art.width * scale)), max(1, int(art.height * scale)))
    resized = art.resize(new_size, Image.Resampling.LANCZOS)
    if fit == "cover":
        left = max(0, (resized.width - box_w) // 2)
        top = max(0, (resized.height - box_h) // 2)
        return resized.crop((left, top, left + box_w, top + box_h))
    return resized


def apply_opacity(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 0.999:
        return image
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: int(value * opacity))
    result.putalpha(alpha)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", type=Path, default=DEFAULT_TEMPLATES)
    parser.add_argument("--template-key", help="Preview template key from preview-templates.json.")
    parser.add_argument("--reference-image", type=Path, help="Override reference/background image.")
    parser.add_argument("--art", type=Path, required=True, help="Print artwork PNG to overlay.")
    parser.add_argument("--box", type=parse_box, help="Normalized overlay box: x,y,width,height.")
    parser.add_argument("--fit", choices=["contain", "cover"], default="contain", help="Use cover to crop full-wrap art into the visible mockup area.")
    parser.add_argument("--opacity", type=float, default=0.94)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    template: dict[str, Any] = {}
    if args.template_key:
        templates = load_json(args.templates).get("templates", {})
        if args.template_key not in templates:
            raise SystemExit(f"Unknown template key {args.template_key!r}. Available: {', '.join(sorted(templates))}")
        template = templates[args.template_key]

    reference_path = args.reference_image or template.get("reference_image")
    if not reference_path:
        raise SystemExit("--reference-image is required when no template key is used.")
    reference_path = resolve_repo_path(reference_path)
    art_path = resolve_repo_path(args.art)
    box = args.box or tuple(template.get("art_box", []))
    if len(box) != 4:
        raise SystemExit("--box is required when the template has no art_box.")

    base = Image.open(reference_path).convert("RGBA")
    art = Image.open(art_path).convert("RGBA")
    x_frac, y_frac, w_frac, h_frac = [float(value) for value in box]
    box_px = (
        int(base.width * x_frac),
        int(base.height * y_frac),
        int(base.width * w_frac),
        int(base.height * h_frac),
    )
    fitted = apply_opacity(fit_image(art, (box_px[2], box_px[3]), args.fit), args.opacity)
    x = box_px[0] + (box_px[2] - fitted.width) // 2
    y = box_px[1] + (box_px[3] - fitted.height) // 2
    base.alpha_composite(fitted, (x, y))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    base.save(args.output, optimize=True)
    print(json.dumps({"output": str(args.output), "reference": str(reference_path), "art": str(art_path), "box": list(box)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
