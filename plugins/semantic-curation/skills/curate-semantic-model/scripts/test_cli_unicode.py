#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Cross-locale JSON stdout portability checks for the command-line helpers."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SCRIPTS = {
    "core": HERE / "semantic_model.py",
    "sources": HERE / "repository_sources.py",
    "coverage": HERE / "ontology_coverage.py",
    "conflicts": HERE / "review_conflicts.py",
}
UNICODE = "不存在 café"


class UnicodeCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="cli-unicode-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.env = os.environ.copy()
        self.env["PYTHONIOENCODING"] = "cp1252"
        self.env["PYTHONUTF8"] = "0"

    def run_cli(self, script, args, expected_code=0):
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS[script]), *map(str, args)],
            cwd=self.root, env=self.env, capture_output=True, check=False,
        )
        self.assertEqual(completed.returncode, expected_code,
                         completed.stderr.decode("ascii", errors="backslashreplace"))
        self.assertNotIn(b"Traceback", completed.stderr)
        self.assertTrue(completed.stdout)
        # All four command summaries are valid UTF-8 JSON and ASCII-only, so
        # writing to a legacy console encoding cannot fail on Unicode data.
        completed.stdout.decode("ascii")
        return json.loads(completed.stdout)

    def write_json(self, path, value):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_core_stdout_escapes_unicode_error_but_report_stays_utf8(self):
        contract = {
            "schema_version": "1", "id": "unicode-cli", "version": "1",
            "types": {"Entity": {"attributes": {"ref": {
                "type": "string", "node_reference_types": ["Entity"]}}}},
            "relations": {}, "require_source_bindings": True, "checks": [],
        }
        model = {
            "schema_version": "1", "contract_id": "unicode-cli", "contract_version": "1",
            "sources": [{"id": "s", "locator": "fixture", "text": UNICODE}],
            "nodes": [{"id": "n", "type": "Entity", "label": "Entity", "definition": UNICODE,
                       "attributes": {"ref": "不存在"}, "source_ids": ["s"]}],
            "relations": [], "bindings": {"s": ["n"]},
        }
        model_path = self.write_json(self.root / "model.json", model)
        contract_path = self.write_json(self.root / "contract.json", contract)
        report_path = self.root / "reports" / "核心报告.json"
        result = self.run_cli("core", ["validate", "--model", model_path, "--contract", contract_path,
                                        "--report", report_path], expected_code=1)
        self.assertEqual(result["errors"][0]["actual"]["id"], "不存在")
        report_bytes = report_path.read_bytes()
        self.assertIn("不存在".encode("utf-8"), report_bytes)
        self.assertEqual(json.loads(report_bytes)["errors"][0]["actual"]["id"], "不存在")

    def test_repository_sources_stdout_and_unicode_output_artifact(self):
        source_root = self.root / "fuentes-ç"
        source_root.mkdir()
        (source_root / "spec.txt").write_text("Nombre: 不存在\n", encoding="utf-8")
        output = self.root / "salida-ñ" / "inventario.json"
        output.parent.mkdir()
        result = self.run_cli("sources", ["inventory", "--root", source_root, "--files", "spec.txt",
                                           "--output", output])
        self.assertEqual(result["tool"], "repository-sources")
        raw = output.read_bytes()
        self.assertIn("不存在".encode("utf-8"), raw)
        self.assertEqual(json.loads(raw)["documents"][0]["text"], "Nombre: 不存在\n")

    def test_coverage_stdout_escapes_unicode_output_path_report_stays_utf8(self):
        ontology = self.write_json(self.root / "ontology.json", {"label": UNICODE})
        ontology_hash = hashlib.sha256(ontology.read_bytes()).hexdigest()
        payload = {
            "schema_version": "1",
            "suite": {"id": "unicode-suite", "version": "1", "cases": [
                {"id": "C1", "title": "Caso café", "expected": "Debe conservar 不存在",
                 "method": "Inspect the pinned local artifact."}]},
            "candidates": [{"id": "candidate:unicode", "label": "Ontology café", "ontology": {
                "iri": "https://example.invalid/unicode", "version": "1",
                "artifact": "ontology.json", "sha256": ontology_hash}, "assessments": []}],
        }
        input_path = self.write_json(self.root / "coverage-input.json", payload)
        report_path = self.root / "报告" / "coverage.json"
        report_path.parent.mkdir()
        result = self.run_cli("coverage", ["--input", input_path, "--report", report_path])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["report"], str(report_path.resolve()))
        raw = report_path.read_bytes()
        self.assertIn("不存在".encode("utf-8"), raw)
        self.assertEqual(json.loads(raw)["suite"]["cases"][0]["expected"], "Debe conservar 不存在")

    def test_conflict_review_stdout_escapes_unicode_output_path_report_stays_utf8(self):
        contract = {"schema_version": "1", "id": "unicode-review", "version": "1",
                    "types": {"Entity": {"attributes": {"name": {"type": "string"}}}},
                    "relations": {}, "require_source_bindings": True, "checks": []}
        model = {"schema_version": "1", "contract_id": "unicode-review", "contract_version": "1",
                 "sources": [{"id": "s", "locator": "fixture", "text": UNICODE}],
                 "nodes": [{"id": "n", "type": "Entity", "label": "Entidad", "definition": UNICODE,
                            "attributes": {"name": UNICODE}, "source_ids": ["s"]}],
                 "relations": [], "bindings": {"s": ["n"]}}
        contract_path = self.write_json(self.root / "contract.json", contract)
        model_path = self.write_json(self.root / "model.json", model)
        claims_path = self.write_json(self.root / "claims.json", {
            "schema_version": "1", "functional_predicates": ["name"], "assertions": [
                {"id": "a1", "subject": "n", "predicate": "name", "value": "Alpha",
                 "polarity": "positive", "source_ids": ["s"]},
                {"id": "a2", "subject": "n", "predicate": "name", "value": "Beta",
                 "polarity": "positive", "source_ids": ["s"]},
            ],
        })
        report_path = self.root / "revisión" / "conflicts.json"
        report_path.parent.mkdir()
        result = self.run_cli("conflicts", ["scan", "--model", model_path, "--contract", contract_path,
                                             "--claims", claims_path,
                                             "--report", report_path], expected_code=1)
        self.assertEqual(result["scan_status"], "completed")
        self.assertEqual(result["report"], str(report_path.resolve()))
        raw = report_path.read_bytes()
        self.assertIn("不存在".encode("utf-8"), raw)
        self.assertEqual(json.loads(raw)["findings"][0]["assertions"][0]["evidence"][0]["original_excerpt"], UNICODE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
