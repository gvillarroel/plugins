#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Deterministic installer and registration regressions; no external mutations."""

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("curator", Path(__file__).with_name("curator.py"))
curator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(curator)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kc-installer-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def fake_installation(self):
        root = self.root / "installed"
        root.mkdir()
        python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"fixture; never executed")
        value = {
            "schema_version": 1,
            "installed": True,
            "python": str(python),
            "home": str(self.root / "state"),
            "bundle_sha256": "fixture",
        }
        curator.write_json(root / curator.MARKER, value)
        return root, value

    def test_real_source_has_complete_verified_inventory(self):
        value = curator.verified_bundle()
        self.assertEqual(value["files"], curator.inventory(curator.SOURCE))
        self.assertIn("src/knowledge_catalog/review.html", value["files"])
        self.assertIn("ontology/shapes.ttl", value["files"])

    def test_modified_source_is_rejected_before_install(self):
        source = self.root / "source"
        curator.shutil.copytree(curator.SOURCE, source)
        (source / "README.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 inventory"):
            curator.verified_bundle(source)

    def test_extra_uninventoried_file_is_rejected(self):
        source = self.root / "source"
        curator.shutil.copytree(curator.SOURCE, source)
        (source / "untracked.txt").write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA-256 inventory"):
            curator.verified_bundle(source)

    def test_unsafe_inventory_path_is_rejected(self):
        source = self.root / "source"
        source.mkdir()
        for name in ("../escape", "C:/escape", "folder\\escape", "/escape"):
            with self.subTest(name=name):
                curator.write_json(source / "bundle.json", {"schema_version": 1, "files": {name: "a"}})
                with self.assertRaisesRegex(ValueError, "unsafe"):
                    curator.verified_bundle(source)

    def test_installation_and_state_cannot_mutate_the_skill(self):
        for path in (
            curator.SKILL,
            curator.SKILL / "local-state",
            curator.SKILL.parent,
        ):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "outside"):
                    curator.outside_payload(path, label="Fixture")

    def test_unrelated_destination_is_preserved(self):
        destination = self.root / "unrelated"
        destination.mkdir()
        sentinel = destination / "keep.txt"
        sentinel.write_text("original", encoding="utf-8")
        with self.assertRaises(OSError):
            curator.install(destination, self.root / "state")
        self.assertEqual(sentinel.read_text(), "original")
        self.assertEqual(list(destination.iterdir()), [sentinel])

    def test_overlapping_runtime_and_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "separate"):
            curator.install(self.root / "runtime", self.root / "runtime/state")

    def test_runtime_requires_complete_managed_installation(self):
        root, value = self.fake_installation()
        value["installed"] = False
        curator.write_json(root / curator.MARKER, value)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            curator.installation(root)

    def test_build_does_not_inherit_a_hosts_other_python_runtime(self):
        with patch.dict(
            os.environ,
            {
                "PYTHONHOME": "another-interpreter",
                "PYTHONPATH": "another-stdlib",
                "VIRTUAL_ENV": "host-environment",
            },
        ):
            value = curator.build_environment(self.root)
        self.assertNotIn("PYTHONHOME", value)
        self.assertNotIn("PYTHONPATH", value)
        self.assertNotIn("VIRTUAL_ENV", value)
        self.assertEqual(value["UV_PROJECT_ENVIRONMENT"], str(self.root / ".venv"))

    def test_registration_preserves_other_settings_and_is_idempotent(self):
        root, value = self.fake_installation()
        config = self.root / "desktop/config.json"
        runtime = self.root / "registry"
        original = {
            "mcpServers": {"other": {"command": "other"}},
            "preferences": {"theme": "dark"},
        }
        curator.write_json(config, original)
        with patch.object(curator, "installation", return_value=value):
            first = curator.register(root, config, runtime)
            second = curator.register(root, config, runtime)
        saved = curator.read_json(config)
        self.assertEqual(saved["preferences"], original["preferences"])
        self.assertEqual(saved["mcpServers"]["other"], original["mcpServers"]["other"])
        self.assertTrue(first["desktop_changed"])
        self.assertFalse(second["desktop_changed"] or second["runtime_changed"])
        backups = list(config.parent.glob("config.json.backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(curator.read_json(backups[0]), original)

    def test_conflicting_registration_changes_neither_file(self):
        root, value = self.fake_installation()
        config = self.root / "desktop/config.json"
        runtime = self.root / "registry"
        curator.write_json(config, {"mcpServers": {"kc-curator": {"command": "existing"}}})
        curator.write_json(runtime / "runtime.json", {"python": "existing", "home": "existing"})
        before = (config.read_bytes(), (runtime / "runtime.json").read_bytes())
        with patch.object(curator, "installation", return_value=value):
            with self.assertRaisesRegex(ValueError, "differs"):
                curator.register(root, config, runtime)
        self.assertEqual(before, (config.read_bytes(), (runtime / "runtime.json").read_bytes()))
        self.assertEqual(list(config.parent.glob("*.backup-*")), [])

    def test_explicit_migration_retains_state_and_backs_up_both_files(self):
        root, value = self.fake_installation()
        config = self.root / "desktop/config.json"
        runtime = self.root / "registry"
        curator.write_json(config, {"mcpServers": {"kc-curator": {"command": "existing"}}})
        curator.write_json(
            runtime / "runtime.json",
            {"python": "existing", "home": "existing", "other": 2},
        )
        with patch.object(curator, "installation", return_value=value):
            curator.register(root, config, runtime, replace_existing=True)
        self.assertEqual(
            curator.read_json(runtime / "runtime.json"),
            {"python": value["python"], "home": value["home"], "other": 2},
        )
        self.assertEqual(len(list(runtime.glob("*.backup-*"))), 1)
        self.assertEqual(len(list(config.parent.glob("*.backup-*"))), 1)

    def test_malformed_desktop_config_cannot_modify_runtime(self):
        root, value = self.fake_installation()
        config = self.root / "config.json"
        for body in ("{broken", "[]", '{"mcpServers": []}'):
            with self.subTest(body=body):
                config.write_text(body, encoding="utf-8")
                with patch.object(curator, "installation", return_value=value):
                    with self.assertRaises(ValueError):
                        curator.register(root, config, self.root / "registry")
                self.assertEqual(config.read_text(), body)
                self.assertFalse((self.root / "registry").exists())

    def test_stdio_launch_passes_through_exit_code_and_selected_state(self):
        root, value = self.fake_installation()
        with (
            patch.object(curator, "installation", return_value=value),
            patch.object(curator.subprocess, "call", return_value=9) as call,
        ):
            self.assertEqual(curator.run(root, [], mcp=True), 9)
        arguments, options = call.call_args
        self.assertEqual(arguments[0], [value["python"], "-I", "-m", "knowledge_catalog.server"])
        self.assertEqual(options["env"]["KC_HOME"], value["home"])
        self.assertNotIn("shell", options)


if __name__ == "__main__":
    unittest.main()
