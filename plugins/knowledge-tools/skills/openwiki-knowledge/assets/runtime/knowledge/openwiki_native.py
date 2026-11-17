"""Prepare one reviewed OpenWiki 0.7.1 graph reader for large retained corpora."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import time

from .errors import KnowledgeError
from .openwiki_snapshot import _no_links


SCHEMA = "knowledge-openwiki-native-graph/1"
RECIPE = "openwiki-0.7.1-bounded-graph-reads/1"
CONCURRENCY = 16
UPSTREAM_SHA256 = "f7548f55bb7a01d9097f4ec566660268169d002e46489ff76311d71706e18dcc"
PATCHED_SHA256 = "ca4d2d027b5d02decbc9169a20d642abc0624dba2ed8684204884a5afbf3d88c"
NPM_INTEGRITY = "sha512-o9Fs5JNKByqDBm00QlzbGjEWQaO8qZWTmhRs0bicgH1jxFwfDQbXEMuht7b15xP6WNXVKAJM4gKjgtOSrqFz/A=="
_ORIGINAL = b"    const nodes = await Promise.all(files.map((file) => readNode(file, wikiRoot)));"
_BOUNDED = b"""    // Keep native node order while bounding simultaneously open Markdown files.
    const nodes = new Array(files.length);
    let nextFile = 0;
    await Promise.all(Array.from({ length: Math.min(16, files.length) }, async () => {
        while (nextFile < files.length) {
            const index = nextFile++;
            nodes[index] = await readNode(files[index], wikiRoot);
        }
    }));"""


class NativePreparationError(KnowledgeError):
    """A native graph module differs from its reviewed version or exact recipe."""


def _io(path: Path) -> Path:
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _closed_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise NativePreparationError("The selected package contains duplicate JSON metadata.")
        result[name] = value
    return result


def _file(path: Path, maximum: int) -> bytes:
    _no_links(_io(path))
    info = _io(path).stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > maximum:
        raise NativePreparationError("Native preparation requires bounded ordinary package files.")
    with _io(path).open("rb") as stream:
        data = stream.read(maximum + 1)
    if len(data) != info.st_size:
        raise NativePreparationError("Native package bytes changed while being inspected.")
    return data


def _inspect(package: Path) -> tuple[dict, bytes]:
    root = Path(package).expanduser().absolute()
    _no_links(_io(root))
    root = root.resolve()
    if not _io(root).is_dir():
        raise NativePreparationError("Select the explicit installed OpenWiki package directory.")
    metadata = json.loads(_file(root / "package.json", 1_048_576), object_pairs_hook=_closed_object)
    if not isinstance(metadata, dict) or metadata.get("name") != "openwiki" or metadata.get("version") != "0.7.1":
        raise NativePreparationError("Only the reviewed OpenWiki 0.7.1 package is accepted.")
    graph = root / "dist/visualize/graph.js"
    data = _file(graph, 32_768)
    digest = _sha(data)
    state = "upstream" if digest == UPSTREAM_SHA256 else "bounded-reads" if digest == PATCHED_SHA256 else None
    if state is None:
        raise NativePreparationError("The selected native graph differs from both reviewed byte identities.")
    binding = {"schema": SCHEMA, "package_root": str(root), "graph_path": str(graph),
               "package_name": "openwiki", "package_version": "0.7.1", "recipe": RECIPE,
               "concurrency": CONCURRENCY, "upstream_sha256": UPSTREAM_SHA256,
               "patched_sha256": PATCHED_SHA256, "graph_sha256": digest,
               "state": state, "model_called": False}
    return binding, data


def inspect_openwiki_graph(package: Path) -> dict:
    """Read the closed graph binding without modifying the selected package."""
    try:
        return _inspect(package)[0]
    except NativePreparationError:
        raise
    except (KnowledgeError, OSError, ValueError, TypeError) as exc:
        raise NativePreparationError("The selected native package could not be inspected safely.") from exc


def _replace(pending: Path, graph: Path, package: Path, previous: dict) -> None:
    for attempt in range(6):
        if inspect_openwiki_graph(package) != previous:
            raise NativePreparationError("The selected native package changed before replacement.")
        if _sha(_file(pending, 32_768)) != PATCHED_SHA256:
            raise NativePreparationError("The staged native graph differs from its reviewed recipe.")
        try:
            os.replace(_io(pending), _io(graph))
            return
        except PermissionError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


def prepare_openwiki_graph(package: Path) -> dict:
    """Atomically apply only the reviewed 16-worker graph recipe, idempotently.

    The source hash comes from the integrity-verified published npm 0.7.1
    tarball. Ordered graph nodes, URI links and original document bytes are
    preserved. This operation makes no network requests or language model calls.
    """
    pending: Path | None = None
    try:
        previous, original = _inspect(package)
        if previous["state"] == "bounded-reads":
            return {**previous, "original_sha256": previous["graph_sha256"], "changed": False, "replacements": 0}
        if original.count(_ORIGINAL) != 1:
            raise NativePreparationError("The reviewed native graph replacement must occur exactly once.")
        patched = original.replace(_ORIGINAL, _BOUNDED)
        if _sha(patched) != PATCHED_SHA256:
            raise NativePreparationError("The native graph recipe produced an unexpected byte identity.")
        root, graph = Path(previous["package_root"]), Path(previous["graph_path"])
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".graph.pending-", suffix=".js", dir=_io(graph.parent), delete=False) as stream:
            pending = Path(stream.name)
            stream.write(patched)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(_io(pending), stat.S_IMODE(_io(graph).stat().st_mode))
        _replace(pending, graph, root, previous)
        current = inspect_openwiki_graph(root)
        if current["state"] != "bounded-reads":
            raise NativePreparationError("The published native graph differs from its reviewed recipe.")
        return {**current, "original_sha256": previous["graph_sha256"], "changed": True, "replacements": 1}
    except NativePreparationError:
        raise
    except (KnowledgeError, OSError, ValueError, TypeError) as exc:
        raise NativePreparationError("Native graph preparation failed its exact reviewed byte contract.") from exc
    finally:
        if pending is not None and _io(pending).exists():
            _no_links(_io(pending))
            _io(pending).unlink()
