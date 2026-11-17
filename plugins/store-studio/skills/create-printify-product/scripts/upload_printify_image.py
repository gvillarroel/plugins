#!/usr/bin/env python3
"""Upload an image to Printify Media Library using PRINTIFY_API_TOKEN."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_URL = "https://api.printify.com/v1/uploads/images.json"


def token() -> str:
    value = os.environ.get("PRINTIFY_API_TOKEN", "").strip()
    if not value:
        raise SystemExit("PRINTIFY_API_TOKEN is required.")
    return value


def post_json(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body_text = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Printify upload failed: HTTP {error.code}\n{body_text}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path, help="Local image file to upload as base64.")
    source.add_argument("--url", help="Public image URL for Printify to fetch.")
    parser.add_argument("--file-name", help="Override file name in Printify.")
    parser.add_argument("--output", type=Path, help="Save upload response JSON.")
    args = parser.parse_args()

    if args.url:
        payload = {"file_name": args.file_name or Path(args.url).name or "image.png", "url": args.url}
    else:
        if not args.file.exists():
            raise SystemExit(f"File does not exist: {args.file}")
        if args.file.stat().st_size > 5 * 1024 * 1024:
            print("Warning: Printify recommends URL upload for files larger than 5 MB.", file=sys.stderr)
        payload = {
            "file_name": args.file_name or args.file.name,
            "contents": base64.b64encode(args.file.read_bytes()).decode("ascii"),
        }

    response = post_json(payload)
    text = json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "image_id": response.get("id")}, indent=2))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
