#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Focused tests for the portable native JSON value projection."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import native_json_values as values

SCRIPT_DIR = Path(__file__).resolve().parent


class NumberPolicyTests(unittest.TestCase):
    def test_exact_numeric_controls(self):
        self.assertEqual(values.canonical_number("1"), values.canonical_number("1.0"))
        self.assertEqual(values.canonical_number("1e3"), values.canonical_number("1000.00"))
        self.assertEqual(values.canonical_number("-0.000"), values.canonical_number("0e-9"))
        self.assertNotEqual(values.canonical_number("0.10000000000000001"),
                            values.canonical_number("0.1"))

    def test_numeric_boundaries(self):
        for text in ("01", "+1", "1.", ".1", "1e", "1e123456789"):
            with self.subTest(text=text), self.assertRaises(values.ProjectionError):
                values.canonical_number(text)

    def test_exponent_limit_counts_significant_digits_after_leading_zeroes(self):
        token = "1e" + ("0" * 5000) + "1"
        self.assertEqual(values.canonical_number(token), "1e1")
        parsed, _ = values.parse_document(token.encode("ascii"))
        self.assertEqual(values.literal(parsed)[1]["canonical"], "1e1")


class ParserAndProjectionTests(unittest.TestCase):
    def test_parser_rejects_duplicates_nonfinite_bom_and_surrogate(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xef\xbb\xbf{}', b'"\\ud800"'):
            with self.subTest(raw=raw), self.assertRaises(values.ProjectionError):
                values.parse_document(raw)

    def test_types_empty_arrays_escaped_pointer_and_order(self):
        a, _ = values.parse_document('{"é/~":[],"n":null,"b":false}'.encode())
        b, _ = values.parse_document('{"b":false,"n":null,"é/~":[]}'.encode())
        self.assertEqual(list(sorted(a)), list(sorted(b)))
        self.assertEqual(values.json_pointer_child("", "é/~"), "/é~1~0")
        self.assertEqual(values.literal(None)[0], "null")
        self.assertEqual(values.literal(False)[0], "boolean")
        self.assertEqual(values.literal([])[0], "array")
        self.assertEqual(values.literal({})[0], "object")

    def test_depth_and_count_limits(self):
        nested = ("[" * (values.MAX_DEPTH + 2)) + "0" + ("]" * (values.MAX_DEPTH + 2))
        with self.assertRaises(values.ProjectionError):
            values.parse_document(nested.encode())

    def test_project_hash_pins_and_stable_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "a.json").write_bytes('{"x":1.00,"x/y":null}'.encode())
            model, contract, report = values.project_values(root, ["a.json"])
            self.assertEqual(report["coverage"]["source_status"], "valid")
            self.assertTrue(report["deterministic_self_comparison"]["replay_equal"])
            self.assertEqual(report["documents"][0]["blob_sha256"],
                             hashlib.sha256((root / "a.json").read_bytes()).hexdigest())
            self.assertEqual(report["semantic_status"], "not_run")
            self.assertEqual(len(model["nodes"]), report["counts"]["values"] + 1)
            self.assertEqual(contract["id"], values.POLICY_ID)

    def test_numeric_equivalence_and_array_position(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "doc.json"
            models = []
            for text in ('{"n":1.00,"a":["x","y"]}',
                         '{"a":["x","y"],"n":1e0}',
                         '{"n":1.01,"a":["x","y"]}'):
                path.write_text(text, encoding="utf-8")
                models.append(values.project_values(root, ["doc.json"])[0])
            snapshots = [values.graph.build_snapshot(model, values.contract_document()) for model in models]
            self.assertEqual(snapshots[0]["graph_sha256"], snapshots[1]["graph_sha256"])
            self.assertNotEqual(snapshots[0]["graph_sha256"], snapshots[2]["graph_sha256"])
            array_nodes = [node for node in models[0]["nodes"]
                           if node["type"] == "Claim" and node["attributes"].get("parent_pointer") == "/a"]
            self.assertEqual([node["attributes"]["segment"] for node in array_nodes], ["0", "1"])

    def test_input_alias_components_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "real.json").write_text("{}", encoding="utf-8")
            link = root / "link.json"
            try:
                link.symlink_to(root / "real.json")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(values.ProjectionError):
                values.project_values(root, ["link.json"])

    def test_same_physical_input_aliases_rejected_but_distinct_case_paths_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "data.json").write_text("{}", encoding="utf-8")
            hardlink = root / "hardlink.json"
            try:
                os.link(root / "data.json", hardlink)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable")
            with self.assertRaises(values.ProjectionError) as caught:
                values.project_values(root, ["data.json", "hardlink.json"])
            self.assertEqual(caught.exception.code, "INPUT_ALIAS")

            other_case = root / "DATA.JSON"
            other_case.write_text("{\"different\":true}", encoding="utf-8")
            try:
                same = os.path.samefile(root / "data.json", other_case)
            except OSError:
                same = False
            if not same:
                model, _, _ = values.project_values(root, ["data.json", "DATA.JSON"])
                self.assertEqual(len(model["sources"]), 2)

    def test_evidence_link_preflight_and_incremental_model_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Blank lines create separate inventoried passages and exercise the
            # links-times-values preflight without allocating a large graph.
            (root / "many.json").write_text("[\n" + ",\n".join(["0"] * 20) + "\n]", encoding="utf-8")
            with mock.patch.object(values, "MAX_EVIDENCE_LINKS", 10):
                with self.assertRaises(values.ProjectionError) as caught:
                    values.project_values(root, ["many.json"])
            self.assertEqual(caught.exception.code, "JSON_EVIDENCE_LINK_LIMIT")
            self.assertGreater(caught.exception.actual["evidence_link_occurrences"], 10)

            (root / "small.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(values, "MAX_MODEL_BYTES", 1):
                with self.assertRaises(values.ProjectionError) as caught:
                    values.project_values(root, ["small.json"])
            self.assertEqual(caught.exception.code, "JSON_MODEL_BYTE_LIMIT")

    def test_exact_final_model_budget_includes_provenance_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "small.json").write_text("{}", encoding="utf-8")
            original_bind = values.sources.bind_provenance

            def oversized_but_bounded(inventory, model, origin):
                result = original_bind(inventory, model, origin)
                result["metadata"] = {"extra": "x" * 5000}
                return result

            # The incremental budget accounts for graph rows; exact serialization
            # catches metadata added during source binding before graph assembly.
            with mock.patch.object(values, "MAX_MODEL_BYTES", 3000), \
                    mock.patch.object(values.sources, "bind_provenance", side_effect=oversized_but_bounded), \
                    mock.patch.object(values.graph, "build_snapshot", side_effect=AssertionError("must not build")):
                with self.assertRaises(values.ProjectionError) as caught:
                    values.project_values(root, ["small.json"])
            self.assertEqual(caught.exception.code, "JSON_MODEL_BYTE_LIMIT")
            self.assertEqual(caught.exception.actual["phase"], "final_exact_check")

    def test_origin_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real = root / "origin.json"
            real.write_text("{}", encoding="utf-8")
            link = root / "origin-link.json"
            try:
                link.symlink_to(real)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(values.ProjectionError):
                values._ensure_regular_origin(link)


class CliTests(unittest.TestCase):
    def test_origin_size_limit_fails_before_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, out = base / "input", base / "out"
            root.mkdir()
            out.mkdir()
            (root / "data.json").write_text("{}", encoding="utf-8")
            origin = base / "origin.json"
            origin.write_text("{}", encoding="utf-8")
            argv = ["project", "--root", str(root), "--files", "data.json",
                    "--model-output", str(out / "m.json"), "--contract-output", str(out / "c.json"),
                    "--report-output", str(out / "r.json"), "--origin", str(origin)]
            stdout = io.StringIO()
            with mock.patch.object(values, "MAX_ORIGIN_BYTES", 1), mock.patch("sys.stdout", stdout):
                self.assertEqual(values.main(argv), 2)
            result = json.loads(stdout.getvalue())
            self.assertEqual(result["errors"][0]["code"], "ORIGIN_BYTE_LIMIT")
            self.assertEqual(list(out.iterdir()), [])

    def test_cli_creates_new_outputs_refuses_overwrite_and_keeps_input(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "input"
            out = Path(temp) / "out"
            root.mkdir()
            out.mkdir()
            source = root / "data.json"
            original = '{"μ": [1, 1.0, 1e0]}'.encode("utf-8")
            source.write_bytes(original)
            argv = [sys.executable, str(SCRIPT_DIR / "native_json_values.py"), "project",
                    "--root", str(root), "--files", "data.json",
                    "--model-output", str(out / "model.json"),
                    "--contract-output", str(out / "contract.json"),
                    "--report-output", str(out / "report.json")]
            first = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertEqual(source.read_bytes(), original)
            report = json.loads((out / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["documents"][0]["blob_sha256"], hashlib.sha256(original).hexdigest())
            second = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(second.returncode, 2)
            self.assertEqual(source.read_bytes(), original)

    def test_copied_runtime_is_self_contained(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            runtime = base / "runtime"
            runtime.mkdir()
            for name in ("native_json_values.py", "semantic_model.py", "repository_sources.py", "repository_graph.py"):
                shutil.copy2(SCRIPT_DIR / name, runtime / name)
            inp = base / "input"
            out = base / "out"
            inp.mkdir()
            out.mkdir()
            (inp / "x.json").write_text('{"ok":true}', encoding="utf-8")
            command = [sys.executable, str(runtime / "native_json_values.py"), "project",
                       "--root", str(inp), "--files", "x.json",
                       "--model-output", str(out / "m.json"), "--contract-output", str(out / "c.json"),
                       "--report-output", str(out / "r.json")]
            result = subprocess.run(command, cwd=base, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
