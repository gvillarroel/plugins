"""Loopback-only reviewer. Capability token, Host/Origin checks and escaped rendering."""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def _invalid_constant(_value):
    raise ValueError("Non-finite JSON is unsupported")


def open_panel(flow, *, lineage=False):
    """Reuse a healthy panel or launch one independently of the Claude session."""
    session_path = flow.home / "review-session.json"

    def existing():
        try:
            session = json.loads(session_path.read_text(encoding="utf-8"))
            base, token = session["url"].split("#")
            parsed = urlsplit(base)
            if (
                parsed.scheme != "http"
                or parsed.hostname != "127.0.0.1"
                or parsed.username
                or parsed.password
                or not parsed.port
                or parsed.path != "/"
            ):
                return None
            request = Request(base + "api/state", headers={"Authorization": "Bearer " + token})
            with urlopen(request, timeout=1) as response:
                if response.status == 200:
                    return session["url"]
        except (OSError, ValueError, KeyError):
            return None

    url = existing()
    if not url:
        with (flow.home / "ui.log").open("a", encoding="utf-8") as log:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "knowledge_catalog.cli",
                    "--home",
                    str(flow.home),
                    "ui",
                    "--port",
                    "0",
                    "--no-open",
                ],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
            )
        for _ in range(80):
            time.sleep(0.1)
            url = existing()
            if url:
                break
    if not url:
        raise ValueError("Review panel could not start; run kc ui from the repository")
    base, capability = url.split("#")
    # A fresh query forces a full navigation even when a host reuses an older
    # tab at the same path. Fragment-only navigation would retain stale UI/data.
    url = (
        urlsplit(base)
        ._replace(
            path="/lineage" if lineage else "/",
            query="ui=en&view=" + secrets.token_urlsafe(8),
            fragment=capability,
        )
        .geturl()
    )
    opened = webbrowser.open(url)
    # The capability stays in the human browser and local session file. Never
    # place the authorization fragment in a model-facing tool result.
    return {
        "opened": opened,
        "address": url.split("#")[0],
        "message": "Review the exact revision in your browser. No approval was created.",
    }


def make_server(flow, port=8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(15)

        def log_message(self, *_):
            pass  # Never log capability tokens or local document names.

        def reply(self, status, body, content_type="application/json; charset=utf-8"):
            data = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            script_hashes = " ".join(
                "'sha256-" + base64.b64encode(hashlib.sha256(script.encode()).digest()).decode() + "'"
                for script in re.findall(
                    r"<script>(.*?)</script>", body if isinstance(body, str) else "", re.S
                )
            )
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src "
                + (script_hashes or "'none'")
                + "; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'; connect-src 'self'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(data)

        def valid_host(self):
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != expected_host:
                self.reply(403, {"error": "Invalid Host"})
                return False
            return True

        def authorized(self, mutation=False):
            if not self.valid_host():
                return False
            if not secrets.compare_digest(
                self.headers.get("Authorization", "").encode("utf-8"), f"Bearer {token}".encode()
            ):
                self.reply(401, {"error": "Open the complete review link printed by kc ui"})
                return False
            expected_host = f"127.0.0.1:{self.server.server_port}"
            if mutation and self.headers.get("Origin") != f"http://{expected_host}":
                self.reply(403, {"error": "Invalid Origin"})
                return False
            return True

        def do_GET(self):
            if not self.valid_host():
                return
            if urlsplit(self.path).path == "/":
                self.reply(
                    200,
                    files("knowledge_catalog").joinpath("review.html").read_text(encoding="utf-8"),
                    "text/html; charset=utf-8",
                )
            elif urlsplit(self.path).path == "/lineage":
                from .lineage_interface import render_lineage

                self.reply(200, render_lineage(), "text/html; charset=utf-8")
            elif self.path == "/favicon.ico":
                self.reply(204, "", "image/x-icon")
            elif self.path == "/api/state" and self.authorized():
                self.reply(200, {"config": flow.config(), "proposals": flow.list(), "events": flow.events()})
            elif self.path == "/api/lineage" and self.authorized():
                from .lineage_interface import store

                self.reply(
                    200,
                    {
                        "items": store(flow.home).list(),
                        "config": flow.config(),
                        "proposals": [
                            {key: p[key] for key in ("id", "digest", "status")}
                            | {"title": p["metadata"]["title"]}
                            for p in flow.list()
                        ],
                    },
                )
            elif self.path not in {"/api/state", "/api/lineage"}:
                self.reply(404, {"error": "Not found"})

        def do_POST(self):
            if not self.authorized(mutation=True):
                return
            if self.path != "/api/action":
                self.reply(404, {"error": "Not found"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 1_000_000:
                    raise ValueError("Request body must be between 1 and 1,000,000 bytes")
                content = self.rfile.read(size)
                if len(content) != size:
                    raise ValueError("Incomplete request body")
                body = json.loads(content, parse_constant=_invalid_constant)
                if not isinstance(body, dict):
                    raise ValueError("Request body must be a JSON object")
                if "live" in body and type(body["live"]) is not bool:
                    raise ValueError("live must be a boolean")
                action, proposal_id = body.get("action"), body.get("id")
                if isinstance(action, str) and action.startswith("lineage_"):
                    from .lineage_interface import attach_record, export_record, store

                    lineage = store(flow.home)
                    lineage_id = body.get("id")
                    digest = body.get("expected_digest")
                    if action == "lineage_demo":
                        result = lineage.create_demo(seed=body.get("seed", 42))
                    elif action == "lineage_get":
                        result = lineage.get(lineage_id)
                    elif action == "lineage_revise":
                        result = lineage.revise(lineage_id, body["updates"], expected_digest=digest)
                    elif action == "lineage_approve":
                        result = lineage.approve(
                            lineage_id, expected_digest=digest, reviewer=body["reviewer"]
                        )
                    elif action == "lineage_reject":
                        result = lineage.reject(lineage_id, expected_digest=digest, reason=body["reason"])
                    elif action == "lineage_restore":
                        result = lineage.restore(lineage_id, body["revision"], expected_digest=digest)
                    elif action == "lineage_history":
                        result = {"items": lineage.history(lineage_id)}
                    elif action == "lineage_revision":
                        result = lineage.get_revision(lineage_id, body["revision"])
                    elif action == "lineage_diff":
                        result = lineage.diff(lineage_id, body["from_revision"], body.get("to_revision"))
                    elif action == "lineage_export":
                        record = lineage.get(lineage_id)
                        if digest != record["digest"]:
                            raise ValueError("Lineage changed; reload before exporting")
                        result = export_record(
                            record,
                            body.get("format", "json"),
                            body.get("project", flow.config()["project"]),
                            flow.config()["location"],
                        )
                    elif action == "lineage_attach":
                        result = attach_record(
                            flow, lineage_id, body["proposal_id"], digest, body["proposal_digest"]
                        )
                    else:
                        raise ValueError("Unknown lineage action")
                elif action == "taxonomy_suggest":
                    result = flow.taxonomy_suggestions(
                        proposal_id,
                        column_name=body.get("column_name"),
                        query=body.get("query", ""),
                        expected_digest=body.get("expected_digest"),
                        provider=body.get("provider", "local"),
                    )
                elif action == "revise":
                    result = flow.revise(
                        proposal_id, body["updates"], expected_digest=body.get("expected_digest")
                    )
                elif action == "approve":
                    result = flow.approve(proposal_id, body["digest"], body["reviewer"])
                elif action == "reject":
                    result = flow.reject(
                        proposal_id, body["reason"], expected_digest=body.get("expected_digest")
                    )
                elif action == "plan":
                    if body.get("live") and not flow.config()["project"]:
                        raise ValueError("Configure a GCP project before live planning")
                    result = flow.replan(
                        proposal_id, live=bool(body.get("live")), expected_digest=body.get("expected_digest")
                    )
                elif action == "publish":
                    result = flow.publish(proposal_id, expected_digest=body.get("expected_digest"))
                elif action == "analyze":
                    result = flow.propose(body["path"])
                elif action == "history":
                    result = flow.history(proposal_id, before_revision=body.get("before_revision"), limit=20)
                elif action == "diff":
                    result = flow.diff(proposal_id, body["from_revision"], body.get("to_revision"))
                elif action == "recover":
                    result = flow.recover_publication(proposal_id, body["expected_digest"], body["reason"])
                elif action == "inventory":
                    if not flow.config()["project"]:
                        raise ValueError("Configure a GCP project first")
                    result = flow.client().inventory()
                elif action == "search":
                    if not flow.config()["project"]:
                        raise ValueError("Configure a GCP project first")
                    result = flow.client().search(body["query"], page_token=body.get("page_token", ""))
                else:
                    raise ValueError("Unknown action")
                self.reply(200, result)
            except Exception as exc:
                status = 409 if "changed; reload" in str(exc).lower() else 400
                self.reply(status, {"error": str(exc), "type": type(exc).__name__})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server, f"http://127.0.0.1:{server.server_port}/#{token}"


def serve(flow, port=8765, open_browser=True):
    importlib.import_module("knowledge_catalog.analysis")
    importlib.import_module("knowledge_catalog.ontology")
    server, url = make_server(flow, port)
    session_path = flow.home / "review-session.json"
    session_path.write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
    print(f"Review UI: {url}", flush=True)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if session_path.exists() and json.loads(session_path.read_text(encoding="utf-8")).get("url") == url:
            session_path.unlink()
