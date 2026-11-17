"""Preserve retained documents and explicit processed libraries for OpenWiki.

Migration copies exact bytes, without synchronizing sources or invoking a model.
Immutable evidence is validated independently from the mutable personal wiki.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import time
from typing import Any
from urllib.parse import quote

from .errors import KnowledgeError
from .openwiki_document_io import authorize_document_paths, document_reader, read_document_bytes
from .openwiki_snapshot import _component, _linked, _no_links, _registered_sources, _relative, _text
from .registry import SOURCE_TYPES
from .store import KnowledgeStore


SCHEMA = "knowledge-openwiki-documents/1"
_EXCLUDED = frozenset({
    ".git", ".hg", ".svn", ".env", ".know", ".knowledge", ".codex", ".agents",
    ".ssh", ".aws", ".azure", ".venv", "venv", "node_modules", "__pycache__",
    "config.yaml", "keys.yaml", "source-metadata.yaml", "credentials",
    "credentials.json", "credentials.yaml", "credentials.yml", "secrets.json",
    "secrets.yaml", "secrets.yml", "id_rsa", "id_ed25519",
    ".openwiki-knowledge-cache", ".openwiki-knowledge-results",
})
_ROOT_COMMON = {"id", "kind", "name", "original_root", "prefix", "status", "files", "excluded"}
_SOURCE_FIELDS = {"key", "source_type", "source_id", "layout", "sync_verified", "last_synced_at"}
_FILE_FIELDS = {"id", "root_id", "path", "wiki_path", "original_path", "sha256", "bytes", "text", "native_page"}
_MANIFEST_FIELDS = {"schema", "store_root", "roots", "files", "counts", "unregistered", "navigation", "model_called"}


class DocumentMigrationError(KnowledgeError):
    """A document migration failed its preservation or path-boundary contract."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _excluded(name: str) -> bool:
    folded = name.casefold()
    return folded in _EXCLUDED or folded.startswith(".env.") or folded.endswith(".pyc")


def _native_page(relative: PurePosixPath) -> bool:
    return relative.name.endswith(".md") and relative.name not in {"INSTRUCTIONS.md", "log.md"}


def _read_bytes(path: Path) -> bytes:
    authorize_document_paths([path])
    return read_document_bytes(path)


def _io(path: Path) -> Path:
    """Use Windows extended paths internally without changing manifest paths."""
    if os.name != "nt":
        return path
    value = str(path.absolute())
    if value.startswith("\\\\?\\"):
        return path
    return Path("\\\\?\\UNC\\" + value[2:] if value.startswith("\\\\") else "\\\\?\\" + value)


def _plain(path: Path) -> Path:
    value = str(path)
    if value.startswith("\\\\?\\UNC\\"):
        return Path("\\\\" + value[8:])
    return Path(value[4:]) if value.startswith("\\\\?\\") else path


def _walk(root: Path, *, exclude_controls: bool = True, exclusions: list[dict] | None = None) -> list[Path]:
    """Inventory physical public files and reject portable directory collisions."""
    _no_links(_io(root))
    files: list[Path] = []
    def visit(directory: Path) -> None:
        seen: set[str] = set()
        for entry in sorted(_io(directory).iterdir(), key=lambda item: item.name):
            path = directory / entry.name
            if _linked(_io(path)):
                raise DocumentMigrationError("Document inputs must not contain symbolic links or junctions.")
            _component(path.name)
            if exclude_controls and _excluded(path.name):
                if exclusions is not None:
                    exclusions.append({"path": path.relative_to(root).as_posix(), "reason": "git-control" if path.name.casefold() == ".git" else "credential-or-runtime-control"})
                continue
            folded = path.name.casefold()
            if folded in seen:
                raise DocumentMigrationError("Document inputs contain platform-colliding names.")
            seen.add(folded)
            mode = _io(path).stat().st_mode
            if stat.S_ISDIR(mode):
                visit(path)
            elif stat.S_ISREG(mode):
                files.append(path)
            else:
                raise DocumentMigrationError("Document inputs require ordinary directories and regular files.")
    visit(root)
    return files


def _path(value: Path) -> Path:
    candidate = Path(value).expanduser().absolute()
    try:
        _no_links(_io(candidate))
    except KnowledgeError as exc:
        raise DocumentMigrationError("Document paths must not contain symbolic links or junctions.") from exc
    return candidate.resolve()


def _counts(roots: list[dict], files: list[dict]) -> dict[str, int]:
    sources: dict[tuple[str, str, str], list[dict]] = {}
    for root in roots:
        if root["kind"] == "source":
            sources.setdefault((root["key"], root["source_type"], root["source_id"]), []).append(root)
    return {
        "roots": len(roots), "sources": len(sources),
        "libraries": sum(root["kind"] == "library" for root in roots), "files": len(files),
        "text_files": sum(record["text"] for record in files),
        "binary_files": sum(not record["text"] for record in files),
        "native_pages": sum(record["native_page"] for record in files),
        "native_aliases": sum("native_read_path" in record for record in files),
        "bytes": sum(record["bytes"] for record in files),
        "characters": sum(record.get("characters", 0) for record in files),
        "empty_roots": sum(root["status"] == "empty" for root in roots),
        "missing_roots": sum(root["status"] == "missing" for root in roots),
        "missing_sources": sum(all(row["status"] == "missing" for row in rows) for rows in sources.values()),
        "empty_sources": sum(all(row["status"] != "available" for row in rows) and any(row["status"] == "empty" for row in rows) for rows in sources.values()),
        "sync_unverified_sources": sum(not rows[0]["sync_verified"] for rows in sources.values()),
        "excluded_entries": sum(len(root["excluded"]) for root in roots),
    }


def _unregistered(store_root: Path, registered: list[dict]) -> list[dict]:
    """Report orphan acquisition directories without reading their contents."""
    if not _io(store_root).exists():
        return []
    known = {(source["key"], source["type"], source["id"]) for source in registered}
    result = []
    for key_dir in sorted(_io(store_root).iterdir(), key=lambda item: item.name):
        key = key_dir.name
        if not _io(store_root / key / "metadata.yaml").is_file():
            continue
        _component(key)
        for layout in ("current", "raw", "library"):
            base = store_root / key if layout == "current" else store_root / key / layout
            _no_links(_io(base))
            if not _io(base).is_dir():
                continue
            for type_dir in sorted(_io(base).iterdir(), key=lambda item: item.name):
                family = type_dir.name
                if family not in SOURCE_TYPES or not type_dir.is_dir():
                    continue
                _no_links(type_dir)
                for entry in sorted(type_dir.iterdir(), key=lambda item: item.name):
                    _no_links(entry)
                    if entry.is_dir() and (key, family, entry.name) not in known:
                        _component(entry.name)
                        result.append({"key": key, "layout": layout, "source_type": family,
                                       "source_id": entry.name, "original_root": str(_plain(entry)),
                                       "reason": "unregistered-source-directory"})
    return result


def _inventory(store: KnowledgeStore, libraries: dict[str, Path]) -> dict:
    if not isinstance(libraries, dict):
        raise DocumentMigrationError("Processed libraries must be explicitly named paths.")
    store_root = _path(store.root_override if store.root_override is not None else store.root)
    if _io(store_root).exists() and not _io(store_root).is_dir():
        raise DocumentMigrationError("The selected store must be a directory.")
    registered = _registered_sources(store) if _io(store_root).exists() else []
    roots: list[dict] = []
    for source in registered:
        key, family, source_id = (source[field] for field in ("key", "type", "id"))
        synced = source.get("last_synced_at")
        for layout in ("current", "raw", "library"):
            prefix = PurePosixPath("store", key, layout, family, source_id).as_posix()
            original = store_root / key / family / source_id if layout == "current" else store_root / key / layout / family / source_id
            roots.append({
                "id": _sha(prefix.encode()), "kind": "source", "name": f"{key}/{layout}/{family}/{source_id}",
                "key": key, "source_type": family, "source_id": source_id, "layout": layout,
                "original_root": str(_path(original)), "prefix": prefix,
                "sync_verified": isinstance(synced, str) and bool(synced.strip()),
                "last_synced_at": synced if isinstance(synced, str) and synced.strip() else None,
            })
    names: set[str] = set()
    for name, value in sorted(libraries.items()):
        _component(name)
        if name.casefold() in names:
            raise DocumentMigrationError("Processed library names must be portable and unique.")
        names.add(name.casefold())
        root = _path(value)
        if not _io(root).is_dir():
            raise DocumentMigrationError("Every explicit processed library must exist as a directory.")
        prefix = PurePosixPath("libraries", name).as_posix()
        roots.append({"id": _sha(prefix.encode()), "kind": "library", "name": name,
                      "original_root": str(root), "prefix": prefix})
    roots.sort(key=lambda row: row["prefix"])
    if len({root["prefix"].casefold() for root in roots}) != len(roots):
        raise DocumentMigrationError("Source identities contain platform-colliding paths.")
    seen: set[str] = set()
    files: list[dict] = []
    for root in roots:
        path = Path(root["original_root"])
        if _io(path).exists() and not _io(path).is_dir():
            raise DocumentMigrationError("A registered source path is not a directory.")
        exclusions: list[dict] = []
        public = _walk(path, exclusions=exclusions) if _io(path).exists() else []
        root["excluded"] = exclusions
        root.update(status="available" if public else "empty" if _io(path).exists() else "missing", files=len(public))
        authorize_document_paths([_io(original) for original in public])
        for original in public:
            relative = _relative(original.relative_to(path).as_posix())
            evidence = PurePosixPath("evidence", root["prefix"], relative).as_posix()
            if evidence.casefold() in seen:
                raise DocumentMigrationError("Document inventory contains platform-colliding paths.")
            seen.add(evidence.casefold())
            data = _read_bytes(_io(original))
            text = _text(data)
            record = {
                "id": _sha(evidence.encode()), "root_id": root["id"], "path": evidence,
                "wiki_path": PurePosixPath("runtime", "wiki", "imported", root["prefix"], relative).as_posix(),
                "original_path": relative.as_posix(), "sha256": _sha(data), "bytes": len(data),
                "text": text is not None, "native_page": _native_page(relative),
            }
            if text is not None:
                record["characters"] = len(text)
            if ".." in record["wiki_path"]:
                record["native_read_path"] = f"runtime/wiki/native-files/{record['id']}.txt"
            files.append(record)
    files.sort(key=lambda record: record["path"])
    return {"schema": SCHEMA, "store_root": str(store_root), "roots": roots, "files": files,
            "counts": _counts(roots, files), "unregistered": _unregistered(store_root, registered), "model_called": False}


def plan_document_migration(store: KnowledgeStore, libraries: dict[str, Path], *, io_reader: str = "python", node_command: str = "node") -> dict:
    """Inventory retained source files and explicitly selected libraries without writes.

    Credential configuration is never copied or resolved. Sources without a
    successful synchronization timestamp remain visible as sync-unverified.
    Missing and empty registrations are reported without creating directories.
    """
    try:
        with document_reader(io_reader, node_command):
            return _inventory(store, libraries)
    except DocumentMigrationError:
        raise
    except (KnowledgeError, OSError, ValueError, TypeError) as exc:
        raise DocumentMigrationError("Document inputs could not be inventoried safely.") from exc


def _navigation(manifest: dict) -> dict[str, bytes]:
    """Generate bounded group pages, preserving links inside every imported tree."""
    def encode(lines: list[str]) -> bytes:
        return ("\n".join(lines) + "\n").encode("utf-8")
    def label(value: str) -> str:
        return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    groups: dict[str, list[dict]] = {}
    roots = {root["id"]: root for root in manifest["roots"]}
    for record in manifest["files"]:
        entry = roots[record["root_id"]]
        group = "store/" + entry["key"] if entry["kind"] == "source" else "libraries/" + entry["name"]
        groups.setdefault(group, []).append(record)
    nav = {"index.md": encode(["# OpenWiki document migration", "", "Exact retained documents and assets; no model synthesis was performed.", "",
                                "- [Personal wiki](runtime/wiki/index.md)", "- [Immutable provenance manifest](manifest.json)", ""])}
    overview = ["# Imported knowledge documents", "", "Exact retained documents and assets; no model synthesis was performed.", "",
                f"Preserved files: {manifest['counts']['files']}. Native Markdown pages: {manifest['counts']['native_pages']}.",
                f"Sync-unverified sources: {manifest['counts']['sync_unverified_sources']}. Missing sources: {manifest['counts']['missing_sources']}. Empty sources: {manifest['counts']['empty_sources']}.", ""]
    for group, records in sorted(groups.items()):
        group_id = _sha(group.encode())[:24]
        pages = []
        for position in range(0, len(records), 200):
            number = position // 200 + 1
            page = f"runtime/wiki/migration-index/{group_id}/page-{number:04d}.md"
            lines = [f"# {label(group)}: documents {position + 1}–{min(position + 200, len(records))}", "", "[Collection navigation](index.md)", ""]
            for record in records[position:position + 200]:
                target = "../../" + str(PurePosixPath(record["wiki_path"]).relative_to("runtime/wiki"))
                kind = "Markdown page" if record["native_page"] else "retained asset"
                name = str(PurePosixPath(record["path"]).relative_to("evidence"))
                lines.append(f"- [{label(name)}]({quote(target, safe='/')}) — {kind}")
                if "native_read_path" in record:
                    alias = "../../" + str(PurePosixPath(record["native_read_path"]).relative_to("runtime/wiki"))
                    lines[-1] += f"; [exact native read alias]({quote(alias, safe='/')})"
            nav[page] = encode(lines + [""])
            pages.append(f"- [Documents {position + 1}–{min(position + 200, len(records))}](page-{number:04d}.md)")
        # Collection catalogs are themselves bounded for very large corpora.
        catalogs = []
        for position in range(0, len(pages), 200):
            name = "index.md" if position == 0 else f"catalog-{position // 200 + 1:04d}.md"
            catalogs.append(name)
            links = [f"[Next catalog](catalog-{position // 200 + 2:04d}.md)"] if position + 200 < len(pages) else []
            nav[f"runtime/wiki/migration-index/{group_id}/{name}"] = encode([f"# {label(group)}", "", *pages[position:position + 200], "", *links, ""])
        overview.append(f"- [{label(group)}](migration-index/{group_id}/index.md)")
    # Bound the top-level catalog as well, even when hundreds of keys are present.
    intro, links = overview[:7], overview[7:]
    for position in range(0, max(len(links), 1), 200):
        path = "runtime/wiki/index.md" if position == 0 else f"runtime/wiki/collections-{position // 200 + 1:04d}.md"
        more = [f"[More collections](collections-{position // 200 + 2:04d}.md)"] if position + 200 < len(links) else []
        nav[path] = encode([*intro, *links[position:position + 200], "", *more, ""])
    return nav


def _write(path: Path, data: bytes) -> None:
    _no_links(_io(path))
    _io(path.parent).mkdir(parents=True, exist_ok=True)
    with _io(path).open("xb") as stream:
        stream.write(data)


def _publish(pending: Path, destination: Path) -> None:
    """Tolerate short Windows scanner locks without replacing any destination."""
    for attempt in range(6):
        _no_links(_io(destination))
        if _io(destination).exists():
            raise DocumentMigrationError("Migration output appeared during preparation.")
        try:
            _io(pending).rename(_io(destination))
            return
        except PermissionError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) not in {5, 32, 33} or attempt == 5:
                raise
            time.sleep(0.05 * 2**attempt)


def migrate_documents(store: KnowledgeStore, libraries: dict[str, Path], output: Path, *, io_reader: str = "python", node_command: str = "node") -> dict:
    """Atomically publish a new exact evidence archive and initial native wiki mirror.

    Existing destinations and overlap with any original store or library fail.
    Original byte and membership checks run before publication. The operation
    does not synchronize sources, normalize Markdown, or invoke language models.
    """
    with document_reader(io_reader, node_command) as reader:
        report = _migrate_documents(store, libraries, output, io_reader=io_reader, node_command=node_command)
        return {**report, "io_reader": reader.report()}


def _migrate_documents(store: KnowledgeStore, libraries: dict[str, Path], output: Path, *, io_reader: str, node_command: str) -> dict:
    destination = _path(output)
    if _io(destination).exists():
        raise DocumentMigrationError("Migration output already exists; choose a new directory.")
    plan = plan_document_migration(store, libraries, io_reader=io_reader, node_command=node_command)
    if not plan["files"]:
        raise DocumentMigrationError("No retained document files are available to migrate.")
    inputs = [Path(plan["store_root"]), *(Path(root["original_root"]) for root in plan["roots"])]
    if any(destination.is_relative_to(root) or root.is_relative_to(destination) for root in inputs):
        raise DocumentMigrationError("Migration output overlaps an original input tree.")
    _io(destination.parent).mkdir(parents=True, exist_ok=True)
    _no_links(_io(destination.parent))
    pending = _plain(Path(tempfile.mkdtemp(prefix=f".{destination.name}.pending-", dir=_io(destination.parent))))
    try:
        roots = {root["id"]: Path(root["original_root"]) for root in plan["roots"]}
        for record in plan["files"]:
            original = roots[record["root_id"]].joinpath(*_relative(record["original_path"]).parts)
            _no_links(_io(original))
            data = _read_bytes(_io(original))
            if len(data) != record["bytes"] or _sha(data) != record["sha256"]:
                raise DocumentMigrationError("Original documents changed during migration.")
            _write(pending / record["path"], data)
            _write(pending / record["wiki_path"], data)
            if "native_read_path" in record:
                _write(pending / record["native_read_path"], data)
        navigation = _navigation(plan)
        manifest = {**plan, "navigation": {path: _sha(data) for path, data in navigation.items()}}
        for path, data in navigation.items():
            _write(pending / path, data)
        _write(pending / "manifest.json", _json(manifest))
        checked = validate_document_migration(pending, verify_originals=True, io_reader=io_reader, node_command=node_command)
        if not checked["wiki_mirror_complete"]:
            raise DocumentMigrationError("The initial native wiki mirror is incomplete.")
        _publish(pending, destination)
        return {**checked, "output": str(destination), "wiki": str(destination / "runtime/wiki")}
    except OSError as exc:
        raise DocumentMigrationError("Document migration failed; original inputs were preserved.") from exc
    finally:
        if _io(pending).exists():
            _no_links(_io(pending))
            if pending.parent.resolve() != destination.parent.resolve():
                raise DocumentMigrationError("Migration cleanup escaped its owned output parent.")
            shutil.rmtree(_io(pending))


def _strict_object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for name, value in pairs:
        if name in result:
            raise DocumentMigrationError("Migration manifest contains duplicate JSON members.")
        result[name] = value
    return result


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_manifest(root: Path) -> dict:
    manifest = json.loads(_io(root / "manifest.json").read_text(encoding="utf-8"), object_pairs_hook=_strict_object)
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_FIELDS or manifest["schema"] != SCHEMA or manifest["model_called"] is not False:
        raise DocumentMigrationError("Migration manifest has invalid fields or schema.")
    if not isinstance(manifest["store_root"], str) or not Path(manifest["store_root"]).is_absolute():
        raise DocumentMigrationError("Migration store provenance requires an absolute root.")
    roots, files = manifest["roots"], manifest["files"]
    if not isinstance(roots, list) or not isinstance(files, list) or not files:
        raise DocumentMigrationError("Migration requires a complete nonempty file inventory.")
    root_map: dict[str, dict] = {}
    portable: set[str] = set()
    for entry in roots:
        if not isinstance(entry, dict) or entry.get("kind") not in {"source", "library"}:
            raise DocumentMigrationError("Migration root metadata is invalid.")
        fields = _ROOT_COMMON | (_SOURCE_FIELDS if entry["kind"] == "source" else set())
        if set(entry) != fields or not isinstance(entry["original_root"], str) or not Path(entry["original_root"]).is_absolute():
            raise DocumentMigrationError("Migration root metadata is outside its whitelist.")
        if entry["kind"] == "source":
            key, family, source_id = (_component(entry[field]) for field in ("key", "source_type", "source_id"))
            layout = entry["layout"]
            if layout not in {"current", "raw", "library"}:
                raise DocumentMigrationError("Migration source layout is unsupported.")
            prefix = PurePosixPath("store", key, layout, family, source_id).as_posix()
            synced = entry["last_synced_at"]
            if family not in SOURCE_TYPES or type(entry["sync_verified"]) is not bool or entry["sync_verified"] != (isinstance(synced, str) and bool(synced.strip())) or synced is not None and not isinstance(synced, str):
                raise DocumentMigrationError("Migration source synchronization provenance is invalid.")
            original = Path(manifest["store_root"]) / key / family / source_id if layout == "current" else Path(manifest["store_root"]) / key / layout / family / source_id
            if entry["name"] != f"{key}/{layout}/{family}/{source_id}" or Path(entry["original_root"]) != original:
                raise DocumentMigrationError("Migration source provenance does not match its identity.")
        else:
            prefix = PurePosixPath("libraries", _component(entry["name"])).as_posix()
        if entry["prefix"] != prefix or entry["id"] != _sha(prefix.encode()) or entry["id"] in root_map or prefix.casefold() in portable:
            raise DocumentMigrationError("Migration root identities collide or differ from their paths.")
        portable.add(prefix.casefold())
        if entry["status"] not in {"available", "empty", "missing"} or not _integer(entry["files"]) or (entry["status"] == "available") != (entry["files"] > 0):
            raise DocumentMigrationError("Migration root status does not match its inventory.")
        if not isinstance(entry["excluded"], list):
            raise DocumentMigrationError("Migration exclusions require an explicit inventory.")
        excluded_paths: set[str] = set()
        for excluded in entry["excluded"]:
            if not isinstance(excluded, dict) or set(excluded) != {"path", "reason"}:
                raise DocumentMigrationError("Migration exclusion metadata is outside its whitelist.")
            path = _relative(excluded["path"])
            expected_reason = "git-control" if path.name.casefold() == ".git" else "credential-or-runtime-control"
            if not _excluded(path.name) or excluded["reason"] != expected_reason or str(path).casefold() in excluded_paths:
                raise DocumentMigrationError("Migration exclusion metadata has invalid paths or reasons.")
            excluded_paths.add(str(path).casefold())
        root_map[entry["id"]] = entry
    expected: set[str] = set()
    portable.clear()
    per_root = {identity: 0 for identity in root_map}
    for record in files:
        if not isinstance(record, dict) or type(record.get("text")) is not bool or type(record.get("native_page")) is not bool or set(record) != _FILE_FIELDS | ({"characters"} if record.get("text") else set()) | ({"native_read_path"} if "native_read_path" in record else set()):
            raise DocumentMigrationError("Migration file metadata is outside its whitelist.")
        entry = root_map.get(record["root_id"])
        if entry is None:
            raise DocumentMigrationError("Migration file references an unknown input root.")
        relative = _relative(record["original_path"])
        if any(_excluded(part) for part in relative.parts):
            raise DocumentMigrationError("Migration inventory includes excluded control files.")
        path = PurePosixPath("evidence", entry["prefix"], relative).as_posix()
        wiki_path = PurePosixPath("runtime", "wiki", "imported", entry["prefix"], relative).as_posix()
        if record["path"] != path or record["wiki_path"] != wiki_path or record["id"] != _sha(path.encode()) or path.casefold() in portable:
            raise DocumentMigrationError("Migration file identity or portable path is invalid.")
        alias = f"runtime/wiki/native-files/{record['id']}.txt" if ".." in wiki_path else None
        if ("native_read_path" in record) != (alias is not None) or alias is not None and record["native_read_path"] != alias:
            raise DocumentMigrationError("Migration native read alias differs from its exact file identity.")
        portable.add(path.casefold())
        target = root / path
        _no_links(_io(target))
        data = _read_bytes(_io(target))
        text = _text(data)
        if not _integer(record["bytes"]) or record["bytes"] != len(data) or record["sha256"] != _sha(data) or record["text"] != (text is not None):
            raise DocumentMigrationError("Immutable migrated evidence differs from its manifest.")
        if record["native_page"] != _native_page(relative) or text is not None and (not _integer(record["characters"]) or record["characters"] != len(text)):
            raise DocumentMigrationError("Migration text metadata differs from exact evidence bytes.")
        expected.add(path)
        per_root[entry["id"]] += 1
    expected_counts = _counts(roots, files)
    if isinstance(manifest["counts"], dict) and "native_aliases" not in manifest["counts"] and expected_counts["native_aliases"] == 0:
        # Initial schema-1 publications predate optional native read aliases.
        expected_counts.pop("native_aliases")
    if any(entry["files"] != per_root[identity] for identity, entry in root_map.items()) or manifest["counts"] != expected_counts or not all(_integer(value) for value in manifest["counts"].values()):
        raise DocumentMigrationError("Migration aggregate counts differ from their inventories.")
    if not isinstance(manifest["unregistered"], list):
        raise DocumentMigrationError("Unregistered source diagnostics require a list.")
    for entry in manifest["unregistered"]:
        if not isinstance(entry, dict) or set(entry) != {"key", "layout", "source_type", "source_id", "original_root", "reason"}:
            raise DocumentMigrationError("Unregistered source diagnostics are outside their whitelist.")
        for field in ("key", "source_type", "source_id"):
            _component(entry[field])
        if entry["layout"] not in {"current", "raw", "library"} or entry["source_type"] not in SOURCE_TYPES or entry["reason"] != "unregistered-source-directory":
            raise DocumentMigrationError("Unregistered source identity is invalid.")
        original = Path(manifest["store_root"]) / entry["key"] / entry["source_type"] / entry["source_id"] if entry["layout"] == "current" else Path(manifest["store_root"]) / entry["key"] / entry["layout"] / entry["source_type"] / entry["source_id"]
        if entry["original_root"] != str(original):
            raise DocumentMigrationError("Unregistered source provenance escaped the store.")
    navigation = _navigation(manifest)
    if not isinstance(manifest["navigation"], dict) or manifest["navigation"] != {path: _sha(data) for path, data in navigation.items()}:
        raise DocumentMigrationError("Migration navigation metadata is invalid.")
    if _sha(_read_bytes(_io(root / "index.md"))) != manifest["navigation"]["index.md"]:
        raise DocumentMigrationError("Immutable migration navigation has changed.")
    immutable = _walk(root / "evidence", exclude_controls=False)
    if {path.relative_to(root).as_posix() for path in immutable} != expected:
        raise DocumentMigrationError("Immutable evidence membership differs from its inventory.")
    for path in _io(root).iterdir():
        if path.name not in {"manifest.json", "index.md", "evidence", "runtime"}:
            raise DocumentMigrationError("Migration output contains undeclared immutable files.")
    return manifest


def _wiki_mirror(root: Path, manifest: dict) -> dict:
    expected = {record["wiki_path"]: record["sha256"] for record in manifest["files"]}
    expected.update({record["native_read_path"]: record["sha256"] for record in manifest["files"] if "native_read_path" in record})
    expected.update({path: digest for path, digest in manifest["navigation"].items() if path != "index.md"})
    missing: list[str] = []
    changed: list[str] = []
    for path, digest in expected.items():
        target = root / path
        _no_links(_io(target))
        if not _io(target).is_file():
            missing.append(path)
        elif _sha(_read_bytes(_io(target))) != digest:
            changed.append(path)
    wiki = root / "runtime/wiki"
    actual = {path.relative_to(root).as_posix() for path in _walk(wiki, exclude_controls=False)} if _io(wiki).is_dir() else set()
    extra = sorted(actual - set(expected))
    return {"complete": not (missing or changed or extra), "missing": sorted(missing), "changed": sorted(changed), "extra": extra}


def validate_document_migration(output: Path, verify_originals: bool = False, *, io_reader: str = "python", node_command: str = "node") -> dict:
    """Verify immutable evidence and report initial wiki mirror integrity separately.

    Later native wiki edits do not invalidate retained evidence. With
    ``verify_originals=True``, original registrations, file membership and exact
    bytes must still match. This function performs no writes or model calls.
    """
    with document_reader(io_reader, node_command) as reader:
        report = _validate_document_migration(output, verify_originals)
        return {**report, "io_reader": reader.report()}


def _validate_document_migration(output: Path, verify_originals: bool) -> dict:
    if type(verify_originals) is not bool:
        raise DocumentMigrationError("Original verification must be an explicit boolean.")
    root = _path(output)
    if not _io(root).is_dir():
        raise DocumentMigrationError("The document migration directory does not exist.")
    try:
        _no_links(_io(root / "manifest.json"))
        _no_links(_io(root / "index.md"))
        manifest = _validate_manifest(root)
        if verify_originals:
            libraries = {entry["name"]: Path(entry["original_root"]) for entry in manifest["roots"] if entry["kind"] == "library"}
            current = _inventory(KnowledgeStore(Path(manifest["store_root"])), libraries)
            if "native_aliases" not in manifest["counts"] and current["counts"]["native_aliases"] == 0:
                current["counts"].pop("native_aliases")
            if current != {name: value for name, value in manifest.items() if name != "navigation"}:
                raise DocumentMigrationError("Original input identity, membership or document bytes have changed.")
        mirror = _wiki_mirror(root, manifest)
        return {"schema": SCHEMA, "output": str(root), "manifest_sha256": _sha((root / "manifest.json").read_bytes()),
                "evidence_valid": True, "wiki_mirror_complete": mirror["complete"], "wiki_mirror": mirror,
                "originals_verified": verify_originals, "counts": manifest["counts"],
                "roots": manifest["roots"], "unregistered": manifest["unregistered"],
                "wiki": str(root / "runtime/wiki"), "model_called": False}
    except DocumentMigrationError:
        raise
    except (KnowledgeError, OSError, ValueError, TypeError, KeyError) as exc:
        raise DocumentMigrationError("Document migration could not be validated safely.") from exc
