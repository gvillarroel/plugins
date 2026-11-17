#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Exercise HTTP transport, UTF-8, authentication, and bounded readiness."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import xerj_api as api


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.server.requests.append({
            "method": self.command, "path": self.path, "body": body,
            "auth": self.headers.get("Authorization"),
        })
        status, value, headers = self.server.responses.pop(0) if self.server.responses else (
            200, {"status": "green"}, {}
        )
        self.send_response(status)
        for key, val in headers.items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(value if isinstance(value, bytes) else json.dumps(value).encode())

    do_GET = respond
    do_POST = respond
    do_PUT = respond
    do_DELETE = respond


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.worker.join()

    def setUp(self):
        self.server.requests = []
        self.server.responses = []

    def test_post_preserves_unicode_and_auth(self):
        value = {"text": "café", "nested": {"count": 4}}
        self.server.responses = [(200, value, {})]
        result = api.request_json(self.url, "POST", "/_memory/test", body=json.dumps(value).encode(), auth="ApiKey test-value")
        self.assertEqual(result, value)
        self.assertEqual(self.server.requests[0]["auth"], "ApiKey test-value")
        self.assertEqual(json.loads(self.server.requests[0]["body"]), value)

    def test_bom_body_is_valid_json(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "body.json"
            path.write_text('{"text":"café"}', encoding="utf-8-sig")
            self.assertEqual(json.loads(api.read_body(path)), {"text": "café"})

    def test_invalid_body_sends_no_request(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "bad.json"
            path.write_text("{bad", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                code = api.main(["--url", self.url, "request", "POST", "/write", "--body-file", str(path)])
            self.assertEqual(code, 1)
            self.assertEqual(self.server.requests, [])

    def test_nonfinite_body_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"score":NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                api.read_body(path)

    def test_http_failure_preserves_existing_output(self):
        self.server.responses = [(400, {"error": "private server detail"}, {})]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory) / "saved.json"
            output.write_text("original", encoding="utf-8")
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = api.main(["--url", self.url, "--output", str(output), "request", "POST", "/write"])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(), "original")
            self.assertNotIn("private server detail", error.getvalue())
            self.assertEqual(len(self.server.requests), 1)

    def test_redirect_is_not_followed(self):
        self.server.responses = [(302, {}, {"Location": self.url + "/target"})]
        with self.assertRaises(api.ApiError) as caught:
            api.request_json(self.url, "GET", "/redirect", auth="ApiKey test-value")
        self.assertEqual(caught.exception.status, 302)
        self.assertEqual(len(self.server.requests), 1)

    def test_invalid_response_json(self):
        self.server.responses = [(200, b"plain cat output", {})]
        with self.assertRaisesRegex(api.ApiError, "format=json"):
            api.request_json(self.url, "GET", "/_cat/indices")

    def test_empty_response(self):
        self.server.responses = [(204, b"", {})]
        self.assertIsNone(api.request_json(self.url, "DELETE", "/one"))

    def test_wait_recovers_after_503(self):
        self.server.responses = [(503, {}, {}), (200, {"status": "yellow"}, {})]
        self.assertEqual(api.wait_ready(self.url, seconds=2, timeout=1, auth=None)["status"], "yellow")
        self.assertEqual(len(self.server.requests), 2)

    def test_wait_does_not_retry_auth_failure(self):
        self.server.responses = [(401, {}, {})]
        with self.assertRaises(api.ApiError) as caught:
            api.wait_ready(self.url, seconds=2, timeout=1, auth=None)
        self.assertEqual(caught.exception.status, 401)
        self.assertEqual(len(self.server.requests), 1)

    def test_wait_deadline_on_red_health(self):
        self.server.responses = [(200, {"status": "red"}, {})]
        started = time.monotonic()
        with self.assertRaisesRegex(api.ApiError, "deadline"):
            api.wait_ready(self.url, seconds=0.05, timeout=1, auth=None)
        self.assertLess(time.monotonic() - started, 0.7)

    def test_environment_header_precedence(self):
        with patch.dict(os.environ, {"TEST_XERJ_KEY": "raw", "TEST_XERJ_AUTH": "Bearer complete"}):
            self.assertEqual(api.authorization("TEST_XERJ_KEY", "TEST_XERJ_AUTH"), "Bearer complete")
        with patch.dict(os.environ, {"TEST_XERJ_KEY": "raw", "TEST_XERJ_AUTH": ""}):
            self.assertEqual(api.authorization("TEST_XERJ_KEY", "TEST_XERJ_AUTH"), "ApiKey raw")

    def test_header_injection_is_rejected(self):
        with patch.dict(os.environ, {"TEST_XERJ_AUTH": "ApiKey raw\nOther: value"}):
            with self.assertRaisesRegex(ValueError, "one line"):
                api.authorization("TEST_XERJ_KEY", "TEST_XERJ_AUTH")

    def test_endpoint_preserves_reverse_proxy_prefix(self):
        self.assertEqual(api.endpoint(self.url + "/proxy/", "/_search?q=one"), self.url + "/proxy/_search?q=one")

    def test_slashless_paths_avoid_msys_conversion(self):
        self.assertEqual(api.endpoint(self.url, "index/_search"), self.url + "/index/_search")
        self.assertEqual(api.endpoint(self.url, ""), self.url + "/")

    def test_cli_root_needs_no_slash_argument(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory) / "root.json"
            self.assertEqual(api.main(["--url", self.url, "--output", str(output), "request", "GET"]), 0)
            self.assertEqual(self.server.requests[0]["path"], "/")

    def test_foreign_paths_and_credential_urls_are_rejected(self):
        for path in ("//other.test/", "https://other.test/", "/test#secret"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                api.endpoint(self.url, path)
        for url in ("file:///tmp/local", "http://user:key@127.0.0.1", "http://127.0.0.1?key=value"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                api.endpoint(url, "/_search")

    def test_timeout_values_are_finite_and_positive(self):
        for value in ("0", "-1", "nan", "inf"):
            with self.subTest(value=value), self.assertRaises(Exception):
                api.positive_seconds(value)

    def test_cli_honors_url_and_exact_utf8_output(self):
        self.server.responses = [(200, {"text": "café", "status": "green"}, {})]
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            output = Path(directory) / "nested" / "health.json"
            env = {**os.environ, "XERJ_URL": self.url, "XERJ_AUTH": "", "XERJ_API_KEY": ""}
            result = subprocess.run(
                [sys.executable, str(Path(api.__file__)), "--output", str(output), "wait", "--seconds", "1"],
                env=env, capture_output=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["text"], "café")
            self.assertEqual(result.stdout, b"")


if __name__ == "__main__":
    unittest.main()
