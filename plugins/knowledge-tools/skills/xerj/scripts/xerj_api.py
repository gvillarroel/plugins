#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Send JSON requests to XERJ or wait for a healthy node, without shell quoting."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


class ApiError(Exception):
    def __init__(self, message: str, *, status: int | None = None):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def positive_seconds(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Use a finite number greater than zero.")
    return number


def endpoint(base: str, path: str) -> str:
    parsed = urllib.parse.urlsplit(base)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Use an HTTP(S) node URL without credentials, query, or fragment.")
    if path.startswith("//") or "#" in path or "\\" in path or urllib.parse.urlsplit(path).scheme:
        raise ValueError("Use a node-relative path; in Git Bash omit the leading slash to avoid path conversion.")
    return base.rstrip("/") + "/" + path.lstrip("/")


def authorization(api_key_env: str, auth_env: str) -> str | None:
    full = os.environ.get(auth_env, "").strip()
    key = os.environ.get(api_key_env, "").strip()
    value = full or (f"ApiKey {key}" if key else None)
    if value and ("\r" in value or "\n" in value):
        raise ValueError("Authorization environment value must be one line.")
    return value


def read_body(path: Path | None) -> bytes | None:
    if path is None:
        return None
    # utf-8-sig accepts PowerShell-authored UTF-8 files with a BOM.
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")


def request_json(
    base: str,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    auth: str | None = None,
    timeout: float = 15,
) -> Any:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if auth:
        headers["Authorization"] = auth
    request = urllib.request.Request(endpoint(base, path), data=body, headers=headers, method=method)
    # Never forward an Authorization header to a redirect target.
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        # Server bodies and URLs can contain private text; keep errors minimal.
        raise ApiError(f"XERJ returned HTTP {exc.code}.", status=exc.code) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ApiError("Cannot reach XERJ; check the node URL, TLS, and server logs.") from None
    if not raw.strip():
        return None
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError):
        raise ApiError("XERJ returned invalid JSON; _cat endpoints need ?format=json.") from None


def wait_ready(base: str, *, seconds: float, timeout: float, auth: str | None) -> Any:
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ApiError("XERJ readiness deadline expired; inspect the server logs.")
        try:
            health = request_json(
                base, "GET", "/_cluster/health", auth=auth, timeout=min(timeout, remaining)
            )
            if isinstance(health, dict) and health.get("status") in {"green", "yellow"}:
                return health
        except ApiError as exc:
            if exc.status is not None and exc.status < 500 and exc.status != 429:
                raise
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(0.25, remaining))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("XERJ_URL", "http://127.0.0.1:9200"))
    parser.add_argument("--api-key-env", default="XERJ_API_KEY", help="Environment variable holding a raw key.")
    parser.add_argument("--auth-env", default="XERJ_AUTH", help="Environment variable holding a full header.")
    parser.add_argument("--timeout", type=positive_seconds, default=15, help="Per-request timeout in seconds.")
    parser.add_argument("--output", type=Path, help="Write the successful JSON response to this exact path.")
    commands = parser.add_subparsers(dest="command", required=True)
    wait = commands.add_parser("wait", help="Poll cluster health with a deadline.")
    wait.add_argument("--seconds", type=positive_seconds, default=30)
    request = commands.add_parser("request", help="Send one request; never retry a mutation.")
    request.add_argument("method", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    request.add_argument("path", nargs="?", default="/", help="Node-relative path; omit the leading slash in Git Bash. Default: root.")
    request.add_argument("--body-file", type=Path, help="Read a UTF-8 JSON request body from this file.")
    args = parser.parse_args(argv)
    try:
        auth = authorization(args.api_key_env, args.auth_env)
        if args.command == "wait":
            result = wait_ready(args.url, seconds=args.seconds, timeout=args.timeout, auth=auth)
        else:
            result = request_json(
                args.url, args.method, args.path, body=read_body(args.body_file),
                auth=auth, timeout=args.timeout,
            )
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.buffer.write(rendered.encode("utf-8"))
        return 0
    except (ApiError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
