#!/usr/bin/env python3
"""Build a Printify create-product JSON payload from local product specs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def parse_int_list(value: str | None) -> list[int]:
    if not value:
        return []
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--product-key", required=True)
    parser.add_argument("--placement", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--price", type=int, default=1999, help="Variant price in cents.")
    parser.add_argument("--variant-ids", help="Comma-separated override. Required if spec has no variant IDs.")
    parser.add_argument("--scale", type=float, default=1.0)
    parser.add_argument("--x", type=float, default=0.5)
    parser.add_argument("--y", type=float, default=0.5)
    parser.add_argument("--angle", type=float, default=0.0)
    parser.add_argument("--tags", help="Comma-separated product tags.")
    parser.add_argument("--include-decoration-method", action="store_true", help="Include decoration_method from the spec placeholder if a provider requires it.")
    args = parser.parse_args()

    spec = load_json(args.spec)
    product, placement = product_and_placement(spec, args.product_key, args.placement)
    api = product.get("api", {})
    blueprint_id = api.get("blueprint_id")
    print_provider_id = api.get("print_provider_id")
    if blueprint_id is None or print_provider_id is None:
        raise SystemExit(f"{args.product_key} does not have blueprint_id and print_provider_id. Fetch/select a Printify product first.")

    variant_ids = parse_int_list(args.variant_ids) or list(api.get("variant_ids", []))
    if not variant_ids:
        hint = api.get("variant_lookup_command", "fetch variants from Printify catalog first")
        raise SystemExit(f"{args.product_key} has no variant IDs. Run: {hint}")

    image: dict[str, Any] = {
        "id": args.image_id,
        "x": args.x,
        "y": args.y,
        "scale": args.scale,
        "angle": args.angle,
    }
    placeholder: dict[str, Any] = {
        "position": placement.get("position", args.placement),
        "images": [image],
    }
    decoration_method = api.get("decoration_method")
    if args.include_decoration_method and decoration_method:
        placeholder["decoration_method"] = decoration_method

    payload: dict[str, Any] = {
        "title": args.title,
        "description": args.description,
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": variant_id, "price": args.price, "is_enabled": True} for variant_id in variant_ids],
        "print_areas": [
            {
                "variant_ids": variant_ids,
                "placeholders": [placeholder],
            }
        ],
    }
    if args.tags:
        payload["tags"] = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    print(json.dumps({"output": str(args.output), "variant_count": len(variant_ids)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
