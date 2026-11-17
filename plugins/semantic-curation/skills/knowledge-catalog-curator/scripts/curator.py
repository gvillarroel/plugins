#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Install and run the bundled curator without writing into the skill payload."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

SKILL = Path(__file__).resolve().parents[1]
SOURCE = SKILL / "assets/runtime"
MARKER = "installation.json"


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}")
    return value


def write_json(path: Path, value: dict, *, backup: bool = False) -> bool:
    if path.exists() and read_json(path) == value:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        descriptor, name = tempfile.mkstemp(prefix=path.name + ".backup-", dir=path.parent)
        os.close(descriptor)
        shutil.copy2(path, name)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return True


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("The runtime bundle must not contain symbolic links")
        relative = path.relative_to(root)
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache"} for part in relative.parts):
            continue
        if path.is_file() and relative.as_posix() != "bundle.json":
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def verified_bundle(root: Path = SOURCE) -> dict:
    manifest = read_json(root / "bundle.json")
    files = manifest.get("files")
    if manifest.get("schema_version") != 1 or not isinstance(files, dict) or not files:
        raise ValueError("The runtime bundle manifest is invalid")
    for name in files:
        if (
            not isinstance(name, str)
            or not name
            or "\\" in name
            or PurePosixPath(name).is_absolute()
            or PureWindowsPath(name).drive
            or ".." in PurePosixPath(name).parts
        ):
            raise ValueError("The runtime bundle contains an unsafe file path")
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(encoded).hexdigest() != manifest.get("sha256"):
        raise ValueError("The runtime bundle inventory digest does not match")
    if inventory(root) != files:
        raise ValueError("The runtime bundle files do not match their SHA-256 inventory")
    return manifest


def outside_payload(path: Path, *, label: str) -> Path:
    path = path.expanduser().resolve()
    if path.is_relative_to(SKILL) or SKILL.is_relative_to(path):
        raise ValueError(f"{label} must be outside the installed skill payload and its ancestors")
    return path


def installation(path: Path) -> dict:
    root = path.expanduser().resolve()
    value = read_json(root / MARKER)
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if (
        value.get("schema_version") != 1
        or value.get("installed") is not True
        or value.get("python") != str(python)
        or not python.is_file()
        or not isinstance(value.get("home"), str)
        or not Path(value["home"]).is_absolute()
    ):
        raise ValueError("The installation is incomplete or its runtime paths are invalid; run install first")
    manifest = verified_bundle(root / "source")
    if value.get("bundle_sha256") != manifest["sha256"]:
        raise ValueError("The installed source differs from the recorded runtime bundle")
    return value


def install(destination: Path | None, home: Path | None, *, dev: bool = False) -> dict:
    manifest = verified_bundle()
    root = outside_payload(
        destination or Path.home() / ".knowledge-catalog-curator/installations" / manifest["sha256"][:16],
        label="The installation directory",
    )
    state = outside_payload(home or Path.cwd() / ".kc", label="The state directory")
    if state.is_relative_to(root) or root.is_relative_to(state):
        raise ValueError("Keep the state directory separate from the runtime installation")
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if root.exists():
        saved = read_json(root / MARKER)
        if saved.get("bundle_sha256") != manifest["sha256"] or saved.get("home") != str(state):
            raise ValueError(
                "The destination belongs to a different bundle or state directory; choose another destination"
            )
        if verified_bundle(root / "source")["sha256"] != manifest["sha256"]:
            raise ValueError("Existing runtime source changed; it was preserved")
    else:
        root.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".kc-install-", dir=root.parent) as directory:
            pending = Path(directory) / "installation"
            pending.mkdir()
            shutil.copytree(SOURCE, pending / "source")
            write_json(
                pending / MARKER,
                {
                    "schema_version": 1,
                    "installed": False,
                    "bundle_sha256": manifest["sha256"],
                    "home": str(state),
                    "python": str(python),
                },
            )
            pending.rename(root)
    uv = shutil.which("uv")
    if not uv:
        raise ValueError("Install uv and retry; the verified runtime source was preserved")
    arguments = [
        uv,
        "sync",
        "--project",
        str(root / "source"),
        "--locked",
        "--no-dev",
        "--no-editable",
        "--python",
        "3.12",
    ]
    if dev:
        arguments.extend(["--extra", "dev"])
    environment = build_environment(root)
    subprocess.run(arguments, env=environment, stdout=sys.stderr, check=True)
    # Import from the installed wheel, never from an ambient PYTHONPATH or checkout.
    subprocess.run(
        [
            str(python),
            "-I",
            "-c",
            "import knowledge_catalog; assert knowledge_catalog.__version__ == '0.3.0'",
        ],
        check=True,
    )
    result = {
        "schema_version": 1,
        "installed": True,
        "bundle_sha256": manifest["sha256"],
        "version": manifest["version"],
        "python": str(python),
        "home": str(state),
        "installed_at": datetime.now(UTC).isoformat(),
        "development_dependencies": dev,
    }
    # Do not churn the timestamp on an idempotent install.
    previous = read_json(root / MARKER)
    if previous.get("installed") and previous.get("development_dependencies") == dev:
        result["installed_at"] = previous["installed_at"]
    write_json(root / MARKER, result)
    return {
        **result,
        "installation": str(root),
        "mcp_config": {
            "mcpServers": {
                "kc-curator": {
                    "command": str(python),
                    "args": ["-I", "-m", "knowledge_catalog.server"],
                    "env": {"KC_HOME": str(state)},
                }
            }
        },
    }


def build_environment(root: Path) -> dict[str, str]:
    # A host can inject its own Python library path; isolated builds must not
    # import that interpreter's stdlib into the selected Python 3.12 runtime.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}
    }
    environment["UV_PROJECT_ENVIRONMENT"] = str(root / ".venv")
    return environment


def desktop_config() -> Path:
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def register(root: Path, config: Path, runtime_dir: Path, *, replace_existing: bool = False) -> dict:
    value = installation(root)
    desired_runtime = {"python": value["python"], "home": value["home"]}
    runtime_path = runtime_dir.expanduser().resolve() / "runtime.json"
    config = config.expanduser().resolve()
    if config == runtime_path:
        raise ValueError("Desktop configuration and runtime registration must be different files")
    runtime = read_json(runtime_path) if runtime_path.exists() else {}
    settings = read_json(config) if config.exists() else {}
    servers = settings.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object; existing configuration was preserved")
    desired_entry = {
        "command": value["python"],
        "args": ["-I", "-m", "knowledge_catalog.server"],
        "env": {"KC_HOME": value["home"]},
    }
    conflicts = runtime and any(runtime.get(key) != desired_runtime[key] for key in desired_runtime)
    conflicts = conflicts or servers.get("kc-curator") not in (None, desired_entry)
    if conflicts and not replace_existing:
        raise ValueError(
            "An existing curator registration differs; inspect it and use --replace-existing only for an intended migration"
        )
    servers["kc-curator"] = desired_entry
    # Validate both objects before replacing either. Each file is atomic and backed up.
    runtime_changed = write_json(runtime_path, {**runtime, **desired_runtime}, backup=True)
    desktop_changed = write_json(config, settings, backup=True)
    return {
        "runtime_config": str(runtime_path),
        "desktop_config": str(config),
        "runtime_changed": runtime_changed,
        "desktop_changed": desktop_changed,
        "restart_required": desktop_changed,
    }


def run(root: Path, arguments: list[str], *, mcp: bool = False) -> int:
    value = installation(root)
    environment = {**os.environ, "KC_HOME": value["home"], "PYTHONUNBUFFERED": "1"}
    module = "knowledge_catalog.server" if mcp else "knowledge_catalog.cli"
    if arguments[:1] == ["--"]:
        arguments = arguments[1:]
    return subprocess.call([value["python"], "-I", "-m", module, *arguments], env=environment)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "inspect",
        help="Verify the portable source inventory; no installation or network calls",
    )
    setup = commands.add_parser("install", help="Create an external runtime using the locked dependencies")
    setup.add_argument("--destination", type=Path)
    setup.add_argument("--home", type=Path)
    setup.add_argument(
        "--dev",
        action="store_true",
        help="Include the runtime's development test dependencies",
    )
    launch = commands.add_parser("run", help="Run kc; pass its arguments after --")
    launch.add_argument("--installation", type=Path, required=True)
    launch.add_argument("arguments", nargs=argparse.REMAINDER)
    server = commands.add_parser("mcp", help="Run the installed MCP stdio server")
    server.add_argument("--installation", type=Path, required=True)
    engine = commands.add_parser(
        "install-engine",
        help="Install the checksum-pinned official Open Ontologies executable",
    )
    engine.add_argument("--installation", type=Path, required=True)
    registration = commands.add_parser(
        "register-claude",
        help="Register this runtime with Claude Desktop and the Code launcher",
    )
    registration.add_argument("--installation", type=Path, required=True)
    registration.add_argument("--desktop-config", type=Path)
    registration.add_argument("--runtime-dir", type=Path)
    registration.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            manifest = verified_bundle()
            result = {
                "valid": True,
                "version": manifest["version"],
                "files": len(manifest["files"]),
                "sha256": manifest["sha256"],
            }
        elif args.command == "install":
            result = install(args.destination, args.home, dev=args.dev)
        elif args.command == "run":
            return run(args.installation, args.arguments)
        elif args.command == "mcp":
            return run(args.installation, [], mcp=True)
        elif args.command == "install-engine":
            value = installation(args.installation)
            subprocess.run(
                [
                    value["python"],
                    "-I",
                    str(args.installation.resolve() / "source/scripts/install_open_ontologies.py"),
                ],
                check=True,
            )
            return 0
        else:
            result = register(
                args.installation,
                args.desktop_config or desktop_config(),
                args.runtime_dir or Path.home() / ".knowledge-catalog-curator",
                replace_existing=args.replace_existing,
            )
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(
            json.dumps({"error": str(error), "type": type(error).__name__}),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
