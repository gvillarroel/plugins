#!/usr/bin/env python3
"""Create a Printify product from a JSON payload, with dry-run by default."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE = "https://api.printify.com"


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def post_product(shop_id: str, payload: dict) -> dict:
    request = Request(
        f"{API_BASE}/v1/shops/{shop_id}/products.json",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {env('PRINTIFY_API_TOKEN')}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Printify create product failed: HTTP {error.code}\n{body}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--shop-id", default=os.environ.get("PRINTIFY_SHOP_ID"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--post", action="store_true", help="Actually POST to Printify. Default is dry-run.")
    args = parser.parse_args()

    if not args.payload.exists():
        raise SystemExit(f"Payload file does not exist: {args.payload}")
    payload = json.loads(args.payload.read_text(encoding="utf-8"))

    required = ["title", "description", "blueprint_id", "print_provider_id", "variants", "print_areas"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise SystemExit(f"Payload missing required keys: {', '.join(missing)}")

    shop_id = args.shop_id or ""
    if args.post:
        if not shop_id:
            raise SystemExit("PRINTIFY_SHOP_ID or --shop-id is required when --post is used.")
        response = post_product(shop_id, payload)
    else:
        response = {
            "dry_run": True,
            "endpoint": f"{API_BASE}/v1/shops/{shop_id or '<PRINTIFY_SHOP_ID>'}/products.json",
            "payload_file": str(args.payload),
            "title": payload.get("title"),
            "variant_count": len(payload.get("variants", [])),
            "print_area_count": len(payload.get("print_areas", [])),
            "next_step": "Review the payload and rerun with --post when ready.",
        }

    text = json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"output": str(args.output)}, indent=2))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
