import importlib.util
import json
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "kc_install", Path(__file__).parents[1] / "scripts/install_local.py"
)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def installation(tmp_path):
    repo = tmp_path / "repository"
    python = repo / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(parents=True)
    python.write_text("fixture; never executed")
    return repo, tmp_path / "runtime", tmp_path / "desktop" / "claude_desktop_config.json"


def test_r41_install_preserves_other_servers_and_is_idempotent(tmp_path):
    repo, runtime, config = installation(tmp_path)
    config.parent.mkdir()
    original = {"mcpServers": {"other": {"command": "other-server"}}, "preferences": {"theme": "dark"}}
    config.write_text(json.dumps(original), encoding="utf-8")
    first = installer.install(repo, runtime, config)
    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert saved["preferences"] == original["preferences"]
    assert first["desktop_changed"]
    backups = list(config.parent.glob("*.backup-*"))
    assert len(backups) == 1 and json.loads(backups[0].read_text()) == original
    second = installer.install(repo, runtime, config)
    assert not second["desktop_changed"] and not second["runtime_changed"]
    assert list(config.parent.glob("*.backup-*")) == backups


@pytest.mark.parametrize("invalid", ["{broken", "[]", '{"mcpServers":[]}'])
def test_r41_invalid_desktop_config_does_not_modify_runtime(tmp_path, invalid):
    repo, runtime, config = installation(tmp_path)
    config.parent.mkdir()
    config.write_text(invalid, encoding="utf-8")
    with pytest.raises(ValueError):
        installer.install(repo, runtime, config)
    assert config.read_text(encoding="utf-8") == invalid
    assert not runtime.exists()


def test_r41_conflicting_registration_remains_untouched(tmp_path):
    repo, runtime, config = installation(tmp_path)
    config.parent.mkdir()
    original = {"mcpServers": {"kc-curator": {"command": "different-server"}}}
    config.write_text(json.dumps(original), encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        installer.install(repo, runtime, config)
    assert json.loads(config.read_text()) == original
    assert not runtime.exists()
