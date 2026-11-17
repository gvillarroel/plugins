#!/usr/bin/env python3
"""Validate a PNG against a Printify product placement spec."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from PIL import Image


DEFAULT_SPEC = Path(__file__).resolve().parents[1] / "references" / "product-specs.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def product_and_placement(spec: dict[str, Any], product_key: str, placement_key: str) -> tuple[dict[str, Any], dict[str, Any]]:
    products = spec.get("products", {})
    if product_key not in products:
        raise SystemExit(f"Unknown product key {product_key!r}. Available: {', '.join(sorted(products))}")
    product = products[product_key]
    placements = product.get("placements", {})
    if placement_key not in placements:
        raise SystemExit(f"Unknown placement {placement_key!r}. Available: {', '.join(sorted(placements))}")
    return product, placements[placement_key]


def alpha_stats(image: Image.Image) -> dict[str, Any]:
    if "A" not in image.getbands():
        return {"has_alpha": False, "bbox": None, "min": 255, "max": 255}
    alpha = image.getchannel("A")
    extrema = alpha.getextrema()
    return {"has_alpha": True, "bbox": alpha.getbbox(), "min": extrema[0], "max": extrema[1]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--product-key", required=True)
    parser.add_argument("--placement", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--json", action="store_true", help="Emit only JSON.")
    parser.add_argument("--no-fail", action="store_true", help="Always return exit code 0.")
    args = parser.parse_args()

    spec = load_json(args.spec)
    _, placement = product_and_placement(spec, args.product_key, args.placement)
    required = placement["print_area"]
    expect_transparent = bool(placement.get("default_transparent", True))
    issues: list[str] = []
    warnings: list[str] = []

    if not args.image.exists():
        issues.append("image file does not exist")
        report = {"image": str(args.image), "ok": False, "issues": issues, "warnings": warnings}
        print(json.dumps(report, indent=2))
        return 0 if args.no_fail else 1

    with Image.open(args.image) as image:
        stats = alpha_stats(image)
        report = {
            "image": str(args.image),
            "format": image.format,
            "mode": image.mode,
            "size": list(image.size),
            "product_key": args.product_key,
            "placement": args.placement,
            "required_min_size": [required["width"], required["height"]],
            "expected_transparent": expect_transparent,
            "alpha": stats,
            "issues": issues,
            "warnings": warnings
        }

        if image.format != "PNG":
            issues.append("image is not a PNG")
        if image.size[0] < int(required["width"]) or image.size[1] < int(required["height"]):
            issues.append("image dimensions are smaller than the Printify print area")
        if expect_transparent:
            if not stats["has_alpha"]:
                issues.append("transparent placement expects an alpha channel")
            elif stats["min"] >= 250:
                issues.append("transparent placement has no meaningful transparent pixels")
            if stats["bbox"] is None:
                issues.append("image has no visible non-transparent pixels")
        else:
            if stats["has_alpha"] and stats["min"] < 255:
                warnings.append("opaque placement includes transparent pixels; confirm this is intentional")

    report["ok"] = not issues

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, indent=2))
        if report["ok"]:
            print("OK: asset meets the configured Printify placement checks.")

    if report["ok"] or args.no_fail:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
