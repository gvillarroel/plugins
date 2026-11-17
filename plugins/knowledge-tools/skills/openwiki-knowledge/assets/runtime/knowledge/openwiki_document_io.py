"""Explicit scoped byte readers for exact, network-free document migration."""

from __future__ import annotations

import base64
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
from typing import Iterator

from .errors import KnowledgeError


MAX_CONTROL_BYTES = 1_048_576
MAX_RESPONSE_BYTES = 400_000
MAX_FILE_BYTES = 268_435_456
_ACTIVE: ContextVar[DocumentReader | None] = ContextVar("openwiki_document_reader", default=None)


class DocumentReaderError(KnowledgeError):
    """An explicit reader failed its closed byte-preservation protocol."""


def _canonical(path: Path) -> str:
    value = str(Path(path).absolute())
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    return value[4:] if value.startswith("\\\\?\\") else value


class DocumentReader:
    """Read approved document paths freshly using Python or a closed Node worker."""

    def __init__(self, implementation: str = "python", node_command: str = "node", *, timeout_seconds: float = 120) -> None:
        if not isinstance(implementation, str) or implementation not in {"python", "native-node"}:
            raise DocumentReaderError("Select the explicit python or native-node document reader.")
        if not isinstance(node_command, str) or not node_command or any(char in node_command for char in "\0\r\n"):
            raise DocumentReaderError("The native reader requires an explicit Node executable.")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or not 0 < timeout_seconds < float("inf"):
            raise DocumentReaderError("Document reader deadlines must be finite and positive.")
        self.implementation = implementation
        self.node_command = node_command
        self.timeout_seconds = timeout_seconds
        self._allowed: set[str] = set()
        self._process: subprocess.Popen | None = None
        self._responses: queue.Queue = queue.Queue(maxsize=16)
        self._stopped = threading.Event()
        self._request_id = 0
        self.files_read = 0
        self.bytes_read = 0
        self.node_version: str | None = None
        self.helper_sha256: str | None = None

    def _start(self) -> None:
        if self._process is not None:
            return
        node = shutil.which(self.node_command)
        if not node:
            raise DocumentReaderError("Install Node.js before selecting native-node document reads.")
        helper = Path(__file__).with_name("openwiki_document_reader.mjs")
        if not helper.is_file() or helper.is_symlink():
            raise DocumentReaderError("The bundled native document reader helper is unavailable.")
        environment = {key: value for key, value in os.environ.items() if key not in {"NODE_OPTIONS", "NODE_PATH"}}
        try:
            version = subprocess.run([node, "--version"], capture_output=True, text=True, env=environment, shell=False, timeout=15, check=False)
            match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)\s*", version.stdout)
            if version.returncode or not match or tuple(map(int, match.groups())) < (22, 22, 0):
                raise DocumentReaderError("The native document reader requires Node.js 22.22.0 or newer.")
            self.node_version = version.stdout.strip()
            self.helper_sha256 = hashlib.sha256(helper.read_bytes()).hexdigest()
            self._process = subprocess.Popen([node, str(helper)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                             env=environment, shell=False, bufsize=65536)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DocumentReaderError("The native document reader could not start.") from exc
        process = self._process
        def deliver(value: object) -> None:
            while not self._stopped.is_set():
                try:
                    self._responses.put(value, timeout=0.1)
                    return
                except queue.Full:
                    pass
        def receive() -> None:
            try:
                while True:
                    line = process.stdout.readline(MAX_RESPONSE_BYTES + 1)
                    if not line:
                        deliver(None)
                        return
                    if len(line) > MAX_RESPONSE_BYTES or not line.endswith(b"\n"):
                        deliver(False)
                        return
                    deliver(line)
            except (OSError, ValueError):
                deliver(None)
        threading.Thread(target=receive, name="openwiki-document-reader", daemon=True).start()

    def _send(self, operation: str, **arguments: object) -> tuple[int, float]:
        self._start()
        self._request_id += 1
        request_id = self._request_id
        data = (json.dumps({"id": request_id, "op": operation, **arguments}, ensure_ascii=True, allow_nan=False) + "\n").encode()
        if len(data) > MAX_CONTROL_BYTES:
            raise DocumentReaderError("Native document reader requests exceed the bounded control window.")
        try:
            # The worker consumes stdin continuously; only bounded path requests are sent.
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise DocumentReaderError("The native document reader exited before accepting its request.") from exc
        return request_id, time.monotonic() + self.timeout_seconds

    def _receive(self, request_id: int, deadline: float) -> dict:
        try:
            line = self._responses.get(timeout=max(deadline - time.monotonic(), 0))
        except queue.Empty as exc:
            self.close()
            raise DocumentReaderError("The native document read exceeded its finite deadline.") from exc
        if not line:
            raise DocumentReaderError("The native document reader ended or exceeded its response window.")
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError) as exc:
            raise DocumentReaderError("The native document reader returned invalid JSON.") from exc
        if not isinstance(value, dict) or value.get("id") != request_id or isinstance(value.get("id"), bool):
            raise DocumentReaderError("The native document reader returned an unsolicited response.")
        if value.get("type") == "error":
            raise DocumentReaderError("The native document reader refused or failed the exact approved file read.")
        return value

    def authorize(self, paths: list[Path]) -> None:
        """Allow only exact paths established by the caller's safe public inventory."""
        added = sorted({_canonical(path) for path in paths} - self._allowed)
        if self.implementation == "native-node":
            batch: list[str] = []
            for path in added:
                if not Path(path).is_absolute() or len(path) > 32768:
                    raise DocumentReaderError("Native document paths must be bounded absolute paths.")
                if batch and len(json.dumps({"paths": [*batch, path]}, ensure_ascii=True).encode()) > MAX_CONTROL_BYTES - 128:
                    self._authorize_batch(batch)
                    batch = []
                batch.append(path)
            if batch:
                self._authorize_batch(batch)
        self._allowed.update(added)

    def _authorize_batch(self, paths: list[str]) -> None:
        request_id, deadline = self._send("authorize", paths=paths)
        response = self._receive(request_id, deadline)
        if response != {"id": request_id, "type": "authorized", "count": len(paths)}:
            raise DocumentReaderError("The native reader did not acknowledge its exact approved paths.")

    def read(self, path: Path) -> bytes:
        """Read fresh bytes; successful results are never cached by filename."""
        canonical = _canonical(path)
        if canonical not in self._allowed:
            raise DocumentReaderError("This file is outside the operation's exact approved read inventory.")
        if self.implementation == "python":
            data = path.read_bytes()
        else:
            request_id, deadline = self._send("read", path=canonical)
            start = self._receive(request_id, deadline)
            total = start.get("bytes")
            if set(start) != {"id", "type", "bytes"} or start["type"] != "start" or isinstance(total, bool) or not isinstance(total, int) or not 0 <= total <= MAX_FILE_BYTES:
                raise DocumentReaderError("The native reader returned invalid file-size metadata.")
            output = bytearray()
            while True:
                response = self._receive(request_id, deadline)
                if response.get("type") == "end":
                    if set(response) != {"id", "type", "bytes", "sha256"} or response["bytes"] != total or len(output) != total or response["sha256"] != hashlib.sha256(output).hexdigest():
                        raise DocumentReaderError("The native file read failed its exact byte digest contract.")
                    break
                if set(response) != {"id", "type", "offset", "data"} or response.get("type") != "chunk" or response.get("offset") != len(output) or isinstance(response.get("offset"), bool) or not isinstance(response.get("data"), str):
                    raise DocumentReaderError("The native reader returned invalid file fragments.")
                try:
                    fragment = base64.b64decode(response["data"], validate=True)
                except ValueError as exc:
                    raise DocumentReaderError("The native reader returned invalid binary transport.") from exc
                if not fragment or len(output) + len(fragment) > total:
                    raise DocumentReaderError("The native reader returned out-of-range file fragments.")
                output.extend(fragment)
            data = bytes(output)
        self.files_read += 1
        self.bytes_read += len(data)
        return data

    def report(self) -> dict:
        """Return safe operational provenance without source bytes or credentials."""
        return {"implementation": self.implementation, "node_version": self.node_version,
                "helper_sha256": self.helper_sha256, "files_read": self.files_read, "bytes_read": self.bytes_read}

    def close(self) -> None:
        """Terminate and reap the owned worker on completion or any failure."""
        process = self._process
        if process is None:
            return
        self._process = None
        self._stopped.set()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        for stream in (process.stdin, process.stdout):
            if stream is not None:
                stream.close()


@contextmanager
def document_reader(io_reader: str = "python", node_command: str = "node") -> Iterator[DocumentReader]:
    """Scope an explicit reader to one operation, reusing compatible nested scopes."""
    current = _ACTIVE.get()
    if current is not None and current.implementation == io_reader and current.node_command == node_command:
        yield current
        return
    reader = DocumentReader(io_reader, node_command)
    token = _ACTIVE.set(reader)
    try:
        yield reader
    finally:
        reader.close()
        _ACTIVE.reset(token)


def authorize_document_paths(paths: list[Path]) -> None:
    """Admit an exact safe inventory to the currently selected operation reader."""
    reader = _ACTIVE.get()
    if reader is None:
        raise DocumentReaderError("Document reads require an explicit operation scope.")
    reader.authorize(paths)


def read_document_bytes(path: Path) -> bytes:
    """Read only an approved exact path using the active scoped reader."""
    reader = _ACTIVE.get()
    if reader is None:
        raise DocumentReaderError("Document reads require an explicit operation scope.")
    return reader.read(path)
