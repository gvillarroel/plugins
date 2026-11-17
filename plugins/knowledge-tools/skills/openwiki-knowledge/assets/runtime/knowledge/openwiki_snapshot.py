"""Create and verify immutable, credential-free evidence for OpenWiki ingestion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
from typing import Any, Iterator

import yaml

from .errors import KnowledgeError
from .registry import SOURCE_TYPES
from .store import KnowledgeStore


SCHEMA = "knowledge-openwiki-snapshot/1"
MANIFEST_NAME = "manifest.json"
_SOURCE_FIELDS = {"key", "id", "type", "title", "last_synced_at"}
_FILE_FIELDS = {
    "id", "path", "key", "source_id", "source_type", "original_path",
    "suffix", "sha256", "bytes", "text",
}
_COUNT_FIELDS = {"sources", "files", "text_files", "binary_files", "bytes", "characters"}
_HASH = re.compile(r"[0-9a-f]{64}")
_DEVICE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", re.IGNORECASE)


class SnapshotError(KnowledgeError):
    """A source or evidence snapshot failed a deterministic integrity check."""


def _component(value: Any) -> str:
    if (
        not isinstance(value, str) or not value or value in {".", ".."}
        or value.endswith((" ", ".")) or _DEVICE.fullmatch(value)
        or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in value)
    ):
        raise SnapshotError("Evidence paths require safe, portable path components.")
    return value


def _relative(value: Any) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise SnapshotError("Evidence paths must be relative POSIX paths.")
    path = PurePosixPath(value)
    if path.is_absolute() or str(path) != value:
        raise SnapshotError("Evidence paths must be canonical relative paths.")
    for part in path.parts:
        _component(part)
    return path


def _linked(path: Path) -> bool:
    if path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)()):
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    # Python 3.11 has no Path.is_junction; reject Windows reparse points too.
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _no_links(path: Path) -> None:
    for current in (path, *path.parents):
        if _linked(current):
            raise SnapshotError("Symbolic links and junctions are not accepted in evidence paths.")


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _tree(root: Path, *, exclude_private: bool = False, exclude_runtime: bool = False) -> Iterator[Path]:
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if _linked(path):
            raise SnapshotError("Symbolic links and junctions are not accepted in evidence trees.")
        _component(path.name)
        mode = path.stat().st_mode
        if not stat.S_ISDIR(mode) and not stat.S_ISREG(mode):
            raise SnapshotError("Evidence trees may contain only directories and regular files.")
        if exclude_runtime and path.name == "runtime":
            if not stat.S_ISDIR(mode):
                raise SnapshotError("Snapshot runtime must be a physical directory.")
            # Upstream runtime state may contain secrets. Never inspect that subtree.
            continue
        if exclude_private and path.name in {".git", "source-metadata.yaml"}:
            continue
        yield path
        if stat.S_ISDIR(mode):
            yield from _tree(path, exclude_private=exclude_private)


def _registered_sources(store: KnowledgeStore) -> list[dict[str, Any]]:
    if not store.root.is_dir():
        raise SnapshotError("The active knowledge store does not exist.")
    _no_links(store.root)
    sources: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for key in store.list_collection_keys():
        _component(key)
        _no_links(store.root / key / "metadata.yaml")
        try:
            metadata = store.get_collection_metadata(key)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            raise SnapshotError("Knowledge source registrations could not be read safely.") from exc
        rows = metadata.get("sources")
        if not isinstance(rows, list):
            raise SnapshotError("Knowledge source registrations must be a list.")
        for row in rows:
            if not isinstance(row, dict) or row.get("key", key) != key:
                raise SnapshotError("Knowledge source registration has an invalid key identity.")
            source_id = _component(row.get("id"))
            source_type = _component(row.get("type"))
            if source_type not in SOURCE_TYPES:
                raise SnapshotError("Knowledge source registration has an unsupported type.")
            identity = (key, source_id)
            if identity in identities:
                raise SnapshotError("Knowledge source registrations have duplicate identities.")
            identities.add(identity)
            title = row.get("title")
            if not isinstance(title, str) or not title.strip():
                raise SnapshotError("Knowledge source registration has no valid title.")
            source = {"key": key, "id": source_id, "type": source_type, "title": title}
            if "last_synced_at" in row:
                source["last_synced_at"] = row["last_synced_at"]
            sources.append(source)
    return sorted(sources, key=lambda source: (source["key"], source["type"], source["id"]))


def _text(data: bytes) -> str | None:
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return None


def _counts(sources: list[dict[str, Any]], files: list[dict[str, Any]]) -> dict[str, int]:
    text_files = sum(record["text"] for record in files)
    return {
        "sources": len(sources), "files": len(files), "text_files": text_files,
        "binary_files": len(files) - text_files,
        "bytes": sum(record["bytes"] for record in files),
        "characters": sum(record.get("characters", 0) for record in files),
    }


def _publish_snapshot_directory(pending: Path, destination: Path) -> None:
    """Retry brief Windows scanner locks while preserving absent-only publication."""
    for attempt in range(6):
        _no_links(destination)
        if destination.exists():
            raise SnapshotError("The snapshot destination appeared during preparation.")
        try:
            pending.rename(destination)
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


def prepare_snapshot(store: KnowledgeStore, output: Path, key: str | None = None) -> dict[str, Any]:
    """Copy selected synchronized evidence without modifying the active store.

    Publish a new directory only after its deterministic manifest and original
    bytes pass validation. Source configuration is omitted and credential values
    are never resolved. Existing destinations and overlapping source trees fail.
    """
    registered = _registered_sources(store)
    if key is not None:
        _component(key)
        if key not in store.list_collection_keys():
            raise SnapshotError("The selected knowledge key does not exist.")
    sources = [source for source in registered if key is None or source["key"] == key]
    if not sources:
        raise SnapshotError("No registered sources were selected for the snapshot.")
    destination = Path(output).expanduser().absolute()
    _no_links(destination)
    destination = destination.resolve()
    if destination.exists():
        raise SnapshotError("The snapshot destination already exists; snapshots cannot be overwritten.")
    for source in registered:
        source_dir = store.root / source["key"] / source["type"] / source["id"]
        if _within(destination, source_dir) or _within(source_dir, destination):
            raise SnapshotError("The snapshot destination overlaps an active source tree.")

    inputs: list[tuple[dict[str, Any], Path, PurePosixPath]] = []
    for source in sources:
        synced = source.get("last_synced_at")
        if not isinstance(synced, str) or not synced.strip():
            raise SnapshotError("Every selected source must have a successful synchronization timestamp.")
        source_dir = store.root / source["key"] / source["type"] / source["id"]
        _no_links(source_dir)
        if not source_dir.is_dir():
            raise SnapshotError("A selected source directory is missing.")
        paths = [path for path in _tree(source_dir, exclude_private=True) if path.is_file()]
        if not paths:
            raise SnapshotError("A selected source contains no evidence files.")
        for path in paths:
            relative = _relative(path.relative_to(source_dir).as_posix())
            inputs.append((source, path, relative))

    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".{destination.name}.pending-", dir=destination.parent))
    try:
        files: list[dict[str, Any]] = []
        for source, original, relative in inputs:
            _no_links(original)
            data = original.read_bytes()
            evidence = PurePosixPath("evidence", source["key"], source["type"], source["id"], relative)
            target = pending.joinpath(*evidence.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            text = _text(data)
            record = {
                "id": hashlib.sha256(str(evidence).encode("utf-8")).hexdigest(),
                "path": str(evidence), "key": source["key"], "source_id": source["id"],
                "source_type": source["type"], "original_path": str(relative),
                "suffix": relative.suffix.lower(), "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data), "text": text is not None,
            }
            if text is not None:
                record["characters"] = len(text)
            files.append(record)
        files.sort(key=lambda record: record["path"])
        manifest = {
            "schema": SCHEMA, "okf_version": "0.2", "sources": sources,
            "files": files, "counts": _counts(sources, files),
        }
        (pending / MANIFEST_NAME).write_bytes(
            (json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
        )
        validate_snapshot(pending)
        # rename never replaces a nonempty directory. Check again before the commit.
        _publish_snapshot_directory(pending, destination)
        return manifest
    except (OSError, ValueError) as exc:
        raise SnapshotError("Evidence snapshot preparation failed; the active store was preserved.") from exc
    finally:
        if pending.exists():
            shutil.rmtree(pending)


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise SnapshotError("Snapshot manifest contains a duplicate JSON member.")
        result[name] = value
    return result


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_snapshot(output: Path) -> dict[str, Any]:
    """Return a manifest only when every evidence identity, path and byte agrees."""
    root = Path(output).expanduser().absolute()
    _no_links(root)
    if not root.is_dir():
        raise SnapshotError("The snapshot directory does not exist.")
    try:
        paths = list(_tree(root, exclude_runtime=True))
        manifest = json.loads((root / MANIFEST_NAME).read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
        if not isinstance(manifest, dict) or set(manifest) != {"schema", "okf_version", "sources", "files", "counts"}:
            raise SnapshotError("Snapshot manifest has unexpected or missing fields.")
        if manifest["schema"] != SCHEMA or manifest["okf_version"] != "0.2":
            raise SnapshotError("Snapshot manifest has an unsupported schema or OKF version.")
        sources, files = manifest["sources"], manifest["files"]
        if not isinstance(sources, list) or not sources or not isinstance(files, list) or not files:
            raise SnapshotError("Snapshot manifest requires nonempty source and file inventories.")
        identities: set[tuple[str, str, str]] = set()
        source_ids: set[tuple[str, str]] = set()
        for source in sources:
            if not isinstance(source, dict) or set(source) != _SOURCE_FIELDS:
                raise SnapshotError("Snapshot source metadata is outside the permitted whitelist.")
            source_key, source_type, source_id = (_component(source[field]) for field in ("key", "type", "id"))
            if source_type not in SOURCE_TYPES:
                raise SnapshotError("Snapshot source type is unsupported.")
            if any(not isinstance(source[field], str) or not source[field].strip() for field in ("title", "last_synced_at")):
                raise SnapshotError("Snapshot source metadata requires a title and successful sync timestamp.")
            if (source_key, source_id) in source_ids:
                raise SnapshotError("Snapshot contains duplicate source identities.")
            source_ids.add((source_key, source_id))
            identities.add((source_key, source_type, source_id))
        expected_files = {MANIFEST_NAME}
        expected_dirs: set[str] = set()
        ids: set[str] = set()
        portable_paths: set[str] = set()
        used_sources: set[tuple[str, str, str]] = set()
        for record in files:
            if not isinstance(record, dict) or type(record.get("text")) is not bool:
                raise SnapshotError("Snapshot file metadata has an invalid text classification.")
            required = _FILE_FIELDS | ({"characters"} if record["text"] else set())
            if set(record) != required:
                raise SnapshotError("Snapshot file metadata has unexpected or missing fields.")
            identity = tuple(_component(record[field]) for field in ("key", "source_type", "source_id"))
            if identity not in identities:
                raise SnapshotError("Snapshot file references an unknown source.")
            original = _relative(record["original_path"])
            if any(part in {".git", "source-metadata.yaml"} for part in original.parts):
                raise SnapshotError("Snapshot includes excluded configuration or Git control files.")
            path = _relative(record["path"])
            if path != PurePosixPath("evidence", *identity, original):
                raise SnapshotError("Snapshot evidence path does not match its source identity.")
            if record["path"].casefold() in portable_paths:
                raise SnapshotError("Snapshot contains duplicate or platform-colliding paths.")
            portable_paths.add(record["path"].casefold())
            file_id = record["id"]
            if file_id != hashlib.sha256(str(path).encode("utf-8")).hexdigest() or file_id in ids:
                raise SnapshotError("Snapshot file identity is invalid or duplicated.")
            ids.add(file_id)
            if record["suffix"] != original.suffix.lower() or not _integer(record["bytes"]):
                raise SnapshotError("Snapshot file suffix or byte count is invalid.")
            if not isinstance(record["sha256"], str) or not _HASH.fullmatch(record["sha256"]):
                raise SnapshotError("Snapshot file digest is invalid.")
            target = root.joinpath(*path.parts)
            if not _within(target.resolve(), root.resolve()) or not target.is_file():
                raise SnapshotError("Snapshot evidence file is missing or escapes the snapshot.")
            data = target.read_bytes()
            if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise SnapshotError("Snapshot evidence bytes do not match the manifest.")
            text = _text(data)
            if record["text"] != (text is not None):
                raise SnapshotError("Snapshot evidence text classification does not match its bytes.")
            if record["text"] and (not _integer(record["characters"]) or record["characters"] != len(text)):
                raise SnapshotError("Snapshot evidence character count does not match its text.")
            expected_files.add(str(path))
            expected_dirs.update(str(parent) for parent in path.parents if str(parent) != ".")
            used_sources.add(identity)
        actual_files = {path.relative_to(root).as_posix() for path in paths if path.is_file()}
        actual_dirs = {path.relative_to(root).as_posix() for path in paths if path.is_dir()}
        if actual_files != expected_files or actual_dirs != expected_dirs or used_sources != identities:
            raise SnapshotError("Snapshot file membership does not match the complete source inventory.")
        counts = manifest["counts"]
        if not isinstance(counts, dict) or set(counts) != _COUNT_FIELDS or not all(_integer(value) for value in counts.values()):
            raise SnapshotError("Snapshot counts have invalid fields or values.")
        if counts != _counts(sources, files):
            raise SnapshotError("Snapshot aggregate counts do not match its evidence inventory.")
        return manifest
    except (OSError, ValueError, TypeError) as exc:
        raise SnapshotError("Snapshot manifest or evidence could not be validated.") from exc
