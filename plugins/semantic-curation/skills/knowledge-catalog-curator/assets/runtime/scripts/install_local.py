"""Validate first, then atomically register the local Claude integration."""

import json
import os
import shutil
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path


def read_object(path):
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path.name}; existing configuration was preserved")
    return value


def write_object(path, value):
    if path.exists() and read_object(path) == value:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        shutil.copy2(path, path.with_name(path.name + f".backup-{stamp}-{uuid.uuid4().hex[:8]}"))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent, prefix=".kc-install-", delete=False
        ) as stream:
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


def install(repo, runtime_dir, config_path):
    repo, runtime_dir, config_path = (
        Path(repo).resolve(),
        Path(runtime_dir).resolve(),
        Path(config_path).resolve(),
    )
    python = repo / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        raise ValueError("Create .venv and install this package first")
    home = repo / ".kc"
    runtime_path = runtime_dir / "runtime.json"
    runtime = read_object(runtime_path)
    desired_runtime = {**runtime, "python": str(python), "home": str(home)}
    if runtime and any(runtime.get(key) != desired_runtime[key] for key in ("python", "home")):
        raise ValueError(
            "Existing curator runtime points to another installation; inspect it before replacing"
        )
    config = read_object(config_path)
    servers = config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object; existing configuration was preserved")
    entry = {
        "command": str(python),
        "args": ["-m", "knowledge_catalog.server"],
        "env": {"KC_HOME": str(home)},
    }
    if servers.get("kc-curator") not in (None, entry):
        raise ValueError("Existing kc-curator registration differs; inspect it before replacing")
    servers["kc-curator"] = entry
    # Each file replacement is atomic. Validate both before replacing either;
    # per-file backups support recovery from a disk failure between writes.
    runtime_changed = write_object(runtime_path, desired_runtime)
    desktop_changed = write_object(config_path, config)
    return {
        "desktop_config": str(config_path),
        "runtime_config": str(runtime_path),
        "runtime_changed": runtime_changed,
        "desktop_changed": desktop_changed,
    }


def main():
    repo = Path(__file__).resolve().parents[1]
    if os.name == "nt":
        desktop_dir = Path(os.environ["APPDATA"]) / "Claude"
    elif sys.platform == "darwin":
        desktop_dir = Path.home() / "Library/Application Support/Claude"
    else:
        desktop_dir = Path.home() / ".config/Claude"
    try:
        result = install(
            repo, Path.home() / ".knowledge-catalog-curator", desktop_dir / "claude_desktop_config.json"
        )
    except (OSError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    print(json.dumps(result, indent=2))
    print("Restart Claude Desktop to load the server. Login is handled by Claude.")


if __name__ == "__main__":
    main()
