#!/usr/bin/env python3
"""Fetch Printify catalog data using PRINTIFY_API_TOKEN."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_BASE = "https://api.printify.com"


def token() -> str:
    value = os.environ.get("PRINTIFY_API_TOKEN", "").strip()
    if not value:
        raise SystemExit("PRINTIFY_API_TOKEN is required.")
    return value


def get_json(path: str, query: dict[str, str] | None = None) -> dict | list:
    url = API_BASE + path
    if query:
        url += "?" + urlencode(query)
    request = Request(url, headers={"Authorization": f"Bearer {token()}", "Accept": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Printify request failed: HTTP {error.code}\n{body}") from error


def write_or_print(data: dict | list, output: Path | None) -> None:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        print(json.dumps({"output": str(output)}, indent=2))
    else:
        sys.stdout.write(text)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    blueprints = subparsers.add_parser("blueprints", help="List catalog blueprints.")
    blueprints.add_argument("--output", type=Path)

    providers = subparsers.add_parser("providers", help="List providers for a blueprint.")
    providers.add_argument("--blueprint-id", type=int, required=True)
    providers.add_argument("--output", type=Path)

    variants = subparsers.add_parser("variants", help="List variants for a blueprint/provider pair.")
    variants.add_argument("--blueprint-id", type=int, required=True)
    variants.add_argument("--print-provider-id", type=int, required=True)
    variants.add_argument("--show-out-of-stock", action="store_true")
    variants.add_argument("--output", type=Path)

    args = parser.parse_args()

    if args.command == "blueprints":
        data = get_json("/v1/catalog/blueprints.json")
        write_or_print(data, args.output)
    elif args.command == "providers":
        data = get_json(f"/v1/catalog/blueprints/{args.blueprint_id}/print_providers.json")
        write_or_print(data, args.output)
    elif args.command == "variants":
        query = {"show-out-of-stock": "1"} if args.show_out_of_stock else None
        data = get_json(f"/v1/catalog/blueprints/{args.blueprint_id}/print_providers/{args.print_provider_id}/variants.json", query=query)
        write_or_print(data, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
