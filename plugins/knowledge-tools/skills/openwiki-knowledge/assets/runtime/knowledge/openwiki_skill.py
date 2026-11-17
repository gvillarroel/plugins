"""Package and install a standalone native OpenWiki knowledge skill without know."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

import yaml

from .errors import KnowledgeError
from .openwiki_snapshot import _no_links, _relative


SKILL_NAME = "openwiki-knowledge"
SCHEMA = "openwiki-knowledge-runtime/1"
_EXCLUDED_MODULES = {"cli.py", "openwiki_commands.py", "openwiki_runtime.py"}
_NATIVE_RESOURCES = {"openwiki_document_reader.mjs"}
_TOOLS = ["knowledge_capabilities", "knowledge_runtime_info", "knowledge_query",
          "knowledge_list_source_files", "knowledge_read_source_file", "knowledge_read_result"]
_PYTHON_NAMES = {"python", "python3", "python.exe", "python3.exe"}
_ENV_NAME = re.compile(r"[A-Z_][A-Z0-9_]*\Z")


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _files(root: Path) -> dict[str, Path]:
    _no_links(root)
    if not root.is_dir():
        raise KnowledgeError("The skill resource directory does not exist")
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            _no_links(Path(directory) / name)
        dirs[:] = [name for name in dirs if name != "__pycache__"]
        for name in files:
            path = Path(directory) / name
            if not path.is_file():
                raise KnowledgeError("Skill resources must be regular files")
            if path.suffix == ".pyc":
                continue
            relative = path.relative_to(root).as_posix()
            _relative(relative)
            result[relative] = path
    return result


def _new_file(path: Path, data: bytes) -> None:
    _no_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _no_links(path)
    with path.open("xb") as stream:
        stream.write(data)


def synchronize_skill_resources(skill_root: Path, source_root: Path, *, check: bool = False) -> dict:
    """Maintain byte-identical bundled libraries; runtime never reads these sources."""
    skill = Path(skill_root).expanduser().absolute()
    source = Path(source_root).expanduser().absolute()
    inputs = _files(source)
    modules = {name: path for name, path in inputs.items()
               if (path.suffix == ".py" or name in _NATIVE_RESOURCES) and name not in _EXCLUDED_MODULES}
    if not {"__init__.py", "openwiki_operations.py", "_openwiki_operation_catalog.py"} <= set(modules):
        raise KnowledgeError("The standalone operation library is incomplete")
    target = skill / "assets" / "runtime" / "knowledge"
    _no_links(target)
    actual = _files(target) if target.exists() else {}
    unexpected = set(actual) - set(modules)
    if unexpected:
        raise KnowledgeError("Unexpected bundled library files; review them before synchronizing")
    changed = [name for name, path in sorted(modules.items())
               if name not in actual or actual[name].read_bytes() != path.read_bytes()]
    manifest = {"schema": SCHEMA, "skill": SKILL_NAME,
                "modules": {name: _sha(path.read_bytes()) for name, path in sorted(modules.items())},
                "excluded_entrypoints": sorted(_EXCLUDED_MODULES)}
    manifest_data = _json(manifest).encode("utf-8")
    manifest_path = skill / "runtime-manifest.json"
    manifest_changed = not manifest_path.exists() or manifest_path.read_bytes() != manifest_data
    if check and (changed or manifest_changed):
        raise KnowledgeError("Bundled skill libraries differ from their maintained source")
    if not check:
        for name in changed:
            path = target / name
            _no_links(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(modules[name].read_bytes())
        _no_links(manifest_path)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_bytes(manifest_data)
    return {"check": check, "modules": len(modules), "changed": changed,
            "runtime_sha256": _sha(manifest_data)}


def validate_skill(skill_root: Path) -> dict:
    """Verify standalone resources, module hashes and native skill discovery metadata."""
    root = Path(skill_root).expanduser().absolute()
    files = _files(root)
    required = {"SKILL.md", "requirements.txt", "runtime-manifest.json",
                "scripts/server.py", "scripts/install.py", "scripts/operate.py",
                "scripts/_runtime.py", "scripts/client.py", "scripts/migrate.py",
                "scripts/prepare_openwiki.py"}
    if not required <= set(files):
        raise KnowledgeError("The standalone skill package is incomplete")
    try:
        raw = files["SKILL.md"].read_text(encoding="utf-8")
        if not raw.startswith("---\n"):
            raise ValueError("metadata")
        header, separator, body = raw[4:].partition("\n---\n")
        metadata = yaml.safe_load(header)
        if not separator or not isinstance(metadata, dict) or set(metadata) != {"name", "description"}:
            raise ValueError("metadata")
        description = metadata["description"]
        if (metadata["name"] != SKILL_NAME or not isinstance(description, str)
                or not description.strip() or len(description) > 1024
                or re.search(r"<[/!?]?[A-Za-z]", description) or not body.strip()
                or len(body.splitlines()) >= 500):
            raise ValueError("metadata")
        for relative, path in files.items():
            if path.suffix != ".md":
                continue
            for match in re.finditer(r"\[[^\]\n]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                link = match.group(1).split("#", 1)[0].strip("<>")
                if not link or "://" in link or link.startswith("mailto:"):
                    continue
                linked = (path.parent / link).resolve()
                if not linked.is_relative_to(root.resolve()) or not linked.is_file():
                    raise ValueError("link")
        manifest = json.loads(files["runtime-manifest.json"].read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA or manifest.get("skill") != SKILL_NAME:
            raise ValueError("manifest")
        modules = manifest["modules"]
        if not isinstance(modules, dict) or not modules:
            raise ValueError("modules")
        actual = _files(root / "assets" / "runtime" / "knowledge")
        if set(actual) != set(modules) or any(name in modules for name in _EXCLUDED_MODULES):
            raise ValueError("module inventory")
        if not {"__init__.py", "openwiki_operations.py", "_openwiki_operation_catalog.py"} <= set(modules):
            raise ValueError("operation library")
        for name, digest in modules.items():
            _relative(name)
            if not isinstance(digest, str) or digest != _sha(actual[name].read_bytes()):
                raise ValueError("module identity")
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        raise KnowledgeError("Skill metadata, references or bundled library failed validation") from exc
    identities = {name: _sha(path.read_bytes()) for name, path in sorted(files.items())}
    return {"skill": SKILL_NAME, "files": len(files), "modules": len(modules),
            "package_sha256": _sha(_json(identities).encode()),
            "runtime_sha256": _sha(files["runtime-manifest.json"].read_bytes()),
            "identities": identities, "model_called": False}


def build_skill(output: Path, *, skill_root: Path) -> dict:
    """Publish one absent-only portable bundle after validating its complete contents."""
    skill = Path(skill_root).expanduser().absolute()
    validation = validate_skill(skill)
    destination = Path(output).expanduser().absolute()
    _no_links(destination)
    if destination.exists():
        raise KnowledgeError("Skill output already exists; choose a new bundle directory")
    if destination.is_relative_to(skill) or skill.is_relative_to(destination):
        raise KnowledgeError("Skill output overlaps the source package")
    destination.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix=f".{destination.name}.pending-", dir=destination.parent))
    try:
        for name, path in _files(skill).items():
            _new_file(pending / name, path.read_bytes())
        if validate_skill(pending)["package_sha256"] != validation["package_sha256"]:
            raise KnowledgeError("Copied skill differs from the validated package")
        _no_links(destination)
        if destination.exists():
            raise KnowledgeError("Skill output appeared during preparation")
        pending.rename(destination)
    finally:
        # This path was created by this call inside the verified destination parent.
        if pending.exists():
            _no_links(pending)
            if pending.parent.resolve() != destination.parent.resolve():
                raise KnowledgeError("Temporary bundle cleanup escaped its owned parent")
            shutil.rmtree(pending)
    return {**validation, "bundle": str(destination)}


def load_host_profiles(profile_file: Path | None, io_root: Path, *, resolve_credentials: bool = True) -> dict:
    """Load human-provisioned channels and credential references outside model arguments."""
    if profile_file is None:
        return {"approved_channels": {}, "approved_credentials": {}}
    root = Path(io_root).expanduser().absolute()
    path = Path(profile_file).expanduser().absolute()
    _no_links(root)
    _no_links(path)
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise KnowledgeError("Host profiles must be a regular file inside the I/O root")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(profile, dict) or set(profile) - {"channels", "credentials"}:
            raise ValueError("profile")
        channels, credentials = profile.get("channels", {}), profile.get("credentials", {})
        if not isinstance(channels, dict) or not isinstance(credentials, dict):
            raise ValueError("profile")
        for name, channel in channels.items():
            if not isinstance(name, str) or not name or not isinstance(channel, dict):
                raise ValueError("channel")
            if (set(channel) - {"source_command", "preview_command", "action_command"}
                    or not channel.get("source_command")
                    or any(not isinstance(value, str) or not value or "\0" in value for value in channel.values())):
                raise ValueError("channel")
        resolved = {}
        for name, reference in credentials.items():
            if (not isinstance(name, str) or not name or not isinstance(reference, str)
                    or not re.fullmatch(r"\$env:[A-Z_][A-Z0-9_]*", reference)):
                raise ValueError("credential reference")
            variable = reference.removeprefix("$env:")
            if resolve_credentials:
                value = os.environ.get(variable)
                if value:
                    resolved[name] = value
            else:
                resolved[name] = reference
    except (OSError, ValueError, TypeError) as exc:
        raise KnowledgeError("Invalid host profiles; supply channels and credential environment references") from exc
    return {"approved_channels": channels, "approved_credentials": resolved}


def install_skill(skill_root: Path, runtime: Path, *, store: Path, io_root: Path,
                  allow_writes: bool = False, python_command: str = "python",
                  forward_env: list[str] | None = None, profiles: Path | None = None,
                  allow_desktop_actions: bool = False) -> dict:
    """Install a native skill and its typed MCP companion in an isolated OpenWiki home."""
    skill = Path(skill_root).expanduser().absolute()
    validation = validate_skill(skill)
    home = Path(runtime).expanduser().absolute()
    store_path = Path(store).expanduser().absolute()
    io_path = Path(io_root).expanduser().absolute()
    for path in (home, store_path, io_path):
        _no_links(path)
    if (not isinstance(allow_writes, bool) or not isinstance(allow_desktop_actions, bool)
            or python_command not in _PYTHON_NAMES):
        raise KnowledgeError("Use a boolean write policy and a safe Python command name")
    names = forward_env or []
    if not isinstance(names, list) or any(not isinstance(name, str) or not _ENV_NAME.fullmatch(name) for name in names):
        raise KnowledgeError("Forward environment variable names, never credential values")
    if any(name in {"PYTHONPATH", "PYTHONHOME"} for name in names):
        raise KnowledgeError("The standalone companion does not accept Python import-path overrides")
    profile_definitions = load_host_profiles(profiles, io_path, resolve_credentials=False)
    credential_variables = [reference.removeprefix("$env:")
                            for reference in profile_definitions["approved_credentials"].values()]
    names = sorted(set([*names, *credential_variables]))
    if any(name in {"PYTHONPATH", "PYTHONHOME"} for name in names):
        raise KnowledgeError("Credential profiles cannot forward Python import-path overrides")
    installed = home / "skills" / SKILL_NAME
    config_path = home / "connectors" / "custom-mcp" / "config.json"
    onboarding_path = home / "onboarding.json"
    receipt_path = home / "knowledge-skill-installation.json"
    for path in (installed, config_path, onboarding_path, receipt_path):
        _no_links(path)
        if path.exists():
            raise KnowledgeError("OpenWiki skill or connector state already exists; use a fresh runtime")
    server = installed / "scripts" / "server.py"
    args = ["-I", str(server), "--store", str(store_path), "--io-root", str(io_path)]
    if allow_writes:
        args.append("--allow-writes")
    if allow_desktop_actions:
        args.append("--allow-desktop-actions")
    if profiles is not None:
        args.extend(["--profiles", str(Path(profiles).expanduser().absolute())])
    allowed = _TOOLS + (["knowledge_change"] if allow_writes else [])
    config = {"enabled": True, "mode": "mcp-stdio",
              "transport": {"type": "stdio", "command": python_command, "args": args,
                            "env": {name: name for name in sorted(set(["PATH", *names]))}},
              "allowedTools": allowed, "readOnlyOperations": []}
    onboarding = {"version": 1, "modeId": "personal", "sources": {}, "sourceInstances": [{
        "id": "knowledge-skill", "connectorId": "custom-mcp", "name": "Standalone knowledge skill",
        "connectedAt": "1970-01-01T00:00:00+00:00",
        "ingestionGoal": "Use the installed knowledge skill and its explicit host operation policy."}]}
    build_skill(installed, skill_root=skill)
    _new_file(config_path, _json(config).encode())
    _new_file(onboarding_path, _json(onboarding).encode())
    receipt = {**validation, "runtime": str(home), "installed_skill": str(installed),
               "store": str(store_path), "io_root": str(io_path), "allow_writes": allow_writes,
               "allow_desktop_actions": allow_desktop_actions,
               "profiles_file": str(Path(profiles).expanduser().absolute()) if profiles is not None else None,
               "tools": allowed, "forwarded_environment_names": sorted(set(names)),
               "openwiki_contract": "0.7.1", "requires_know_cli": False,
               "requires_repository_checkout": False, "model_called": False}
    _new_file(receipt_path, _json(receipt).encode())
    return {**receipt, "receipt": str(receipt_path)}
