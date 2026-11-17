#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for importing evidence-bound semantic review proposals."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name("import_semantic_review.py")
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location("import_semantic_review", SCRIPT)
assert spec and spec.loader
importer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = importer
spec.loader.exec_module(importer)

SKILL = SCRIPT.parents[1]
EXAMPLES = SKILL / "assets/examples/semantic-model"


def base_report(collision: bool = False, invalid_head: bool = False):
    model = json.loads((EXAMPLES / "example-model.json").read_text(encoding="utf-8"))
    contract = json.loads((EXAMPLES / "example-contract.json").read_text(encoding="utf-8"))
    if collision:
        model["relations"][0]["id"] = sorted(row["id"] for row in model["nodes"])[0]
    head = copy.deepcopy(model)
    if invalid_head:
        head["nodes"][0]["type"] = "UnknownType"
    return importer.graph.compare_models(model, head, contract)


def proposals(parent, relation_id=None, injection=False):
    model = parent["head"]["model"]
    source = model["sources"][0]
    quote = source["text"]
    if injection:
        quote = "<img src=x onerror=alert(1)>"
        source["text"] = "Evidence " + quote
        parent["base"]["model"]["sources"][0]["text"] = "Evidence " + quote
        parent["head"]["model"]["sources"][0]["text"] = "Evidence " + quote
        parent.pop("review_revision", None)
        parent["review_revision"] = importer.graph.digest(parent)
    relation_id = relation_id or model["relations"][0]["id"]
    return {"schema_version": "1", "parent_review_revision": parent["review_revision"],
            "reviewer": {"kind": "human", "id": "reviewer-1", "artifact_sha256": "a" * 64},
            "findings": [
                {"proposal_id": "node-issue", "side": "head", "collection": "nodes",
                 "entity_id": model["nodes"][0]["id"], "field_pointer": "/definition",
                 "category": "source_support", "summary": "Definition needs review.",
                 "uncertainty": "The quoted passage may be incomplete.",
                 "sources": [{"source_id": source["id"], "quote": quote}]},
                {"proposal_id": "relation-issue", "side": "base", "collection": "relations",
                 "entity_id": relation_id, "field_pointer": "/type",
                 "category": "scope", "summary": "Relation scope may be too broad.",
                 "uncertainty": "Context is limited to this source excerpt.",
                 "sources": [{"source_id": parent["base"]["model"]["sources"][0]["id"], "quote": quote}]},
            ]}


class ImportSemanticReviewTests(unittest.TestCase):
    def test_import_preserves_graph_and_validation_and_binds_new_decision_revision(self):
        parent = base_report()
        parent_subtrees = {key: copy.deepcopy(parent[key]) for key in ("base", "head", "changes", "competency_deltas")}
        proposals_doc = proposals(parent)
        result = importer.import_proposals(parent, proposals_doc, "b" * 64)
        self.assertEqual(result["findings"][:len(parent["findings"])], parent["findings"])
        for key, value in parent_subtrees.items():
            self.assertEqual(result[key], value)
        self.assertEqual(result["semantic_status"], "proposals_imported_unvalidated")
        self.assertEqual(result["summary"]["semantic_proposals"], 2)
        self.assertEqual(result["summary"]["findings"], len(parent["findings"]) + 2)
        self.assertEqual(result["summary"]["new_errors"], parent["summary"]["new_errors"])
        self.assertEqual(result["summary"]["historical_errors"], parent["summary"]["historical_errors"])
        self.assertEqual(result["semantic_review_overlay"]["parent_review_revision"], parent["review_revision"])
        self.assertNotEqual(result["review_revision"], parent["review_revision"])
        self.assertEqual(result["review_revision"], importer.graph.digest({k: v for k, v in result.items() if k != "review_revision"}))

    def test_namespace_collision_keeps_precise_relation_anchor_without_ambiguous_inspect_button(self):
        parent = base_report(collision=True)
        duplicated_id = parent["head"]["model"]["nodes"][0]["id"]
        document = proposals(parent, relation_id=duplicated_id)
        result = importer.import_proposals(parent, document, "c" * 64)
        finding = next(row for row in result["findings"] if row.get("proposal_id") == "relation-issue")
        self.assertNotIn("entity_id", finding)
        self.assertEqual(finding["target"]["collection"], "relations")
        self.assertEqual(finding["target"]["entity_id"], duplicated_id)
        self.assertEqual(finding["diagnostic"]["field_pointer"], "/type")

    def test_permutation_policy_is_canonical_findings_but_raw_artifact_hash_remains_provenance(self):
        parent = base_report()
        document = proposals(parent)
        reversed_doc = copy.deepcopy(document)
        reversed_doc["findings"].reverse()
        left = importer.import_proposals(parent, document, "d" * 64)
        right = importer.import_proposals(parent, reversed_doc, "e" * 64)
        self.assertEqual(left["semantic_review_overlay"]["normalized_proposals_sha256"],
                         right["semantic_review_overlay"]["normalized_proposals_sha256"])
        left_ids = {item["proposal_id"]: item["id"] for item in left["findings"] if item.get("proposal_id")}
        right_ids = {item["proposal_id"]: item["id"] for item in right["findings"] if item.get("proposal_id")}
        self.assertEqual(left_ids, right_ids)
        self.assertNotEqual(left["review_revision"], right["review_revision"])
        exact = importer.import_proposals(parent, document, "d" * 64)
        self.assertEqual(importer.graph.canonical_bytes(left), importer.graph.canonical_bytes(exact))

    def test_rejects_stale_parent_unknown_field_bad_quote_cross_side_and_reimport(self):
        parent = base_report()
        doc = proposals(parent)
        stale = copy.deepcopy(doc)
        stale["parent_review_revision"] = "0" * 64
        with self.assertRaisesRegex(importer.ImportErrorDetail, "parent_review_revision"):
            importer.import_proposals(parent, stale, "f" * 64)
        bad_field = copy.deepcopy(doc)
        bad_field["findings"][0]["field_pointer"] = "/missing"
        with self.assertRaisesRegex(importer.ImportErrorDetail, "existing field"):
            importer.import_proposals(parent, bad_field, "f" * 64)
        bad_quote = copy.deepcopy(doc)
        bad_quote["findings"][0]["sources"][0]["quote"] = "not present in source"
        with self.assertRaisesRegex(importer.ImportErrorDetail, "exact substring"):
            importer.import_proposals(parent, bad_quote, "f" * 64)
        cross = copy.deepcopy(doc)
        head_source = parent["head"]["model"]["sources"][0]
        head_only = head_source["id"]
        parent["base"]["model"]["sources"] = [row for row in parent["base"]["model"]["sources"] if row["id"] != head_only]
        parent.pop("review_revision", None)
        parent["review_revision"] = importer.graph.digest(parent)
        doc["parent_review_revision"] = parent["review_revision"]
        cross["parent_review_revision"] = parent["review_revision"]
        cross["findings"][1]["sources"][0] = {"source_id": head_only, "quote": head_source["text"]}
        with self.assertRaisesRegex(importer.ImportErrorDetail, "only on head"):
            importer.import_proposals(parent, cross, "f" * 64)
        clean_parent = base_report()
        clean_doc = proposals(clean_parent)
        overlaid = importer.import_proposals(clean_parent, clean_doc, "f" * 64)
        with self.assertRaisesRegex(importer.ImportErrorDetail, "already has"):
            importer.import_proposals(overlaid, clean_doc, "f" * 64)


    def test_invalid_candidate_remains_renderable_and_validation_is_unchanged(self):
        parent = base_report(invalid_head=True)
        self.assertEqual(parent["head"]["validation"]["contract_status"], "invalid")
        original_validation = copy.deepcopy(parent["head"]["validation"])
        result = importer.import_proposals(parent, proposals(parent), "2" * 64)
        self.assertEqual(result["head"]["validation"], original_validation)
        self.assertEqual(result["semantic_status"], "proposals_imported_unvalidated")
        importer.renderer.render_report(result)

    def test_cli_creates_new_json_and_html_and_never_overwrites(self):
        parent = base_report()
        proposal_doc = proposals(parent)
        with tempfile.TemporaryDirectory(prefix="semantic-review-import-") as tmp:
            root = Path(tmp)
            report_path, proposal_path = root / "parent.json", root / "proposals.json"
            output_path, html_path = root / "imported.json", root / "imported.html"
            report_path.write_bytes(importer.graph.canonical_bytes(parent))
            proposal_path.write_text(json.dumps(proposal_doc, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, str(SCRIPT), "--report", str(report_path), "--proposals", str(proposal_path),
                       "--output", str(output_path), "--html", str(html_path)]
            first = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            saved = output_path.read_bytes()
            self.assertTrue(html_path.is_file())
            second = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output_path.read_bytes(), saved)
            self.assertEqual(json.loads(saved)["semantic_status"], "proposals_imported_unvalidated")

    def test_field_pointer_escapes_and_array_indices_follow_rfc6901(self):
        self.assertEqual(importer._pointer_value({"a/b": "slash", "01": "object-key"}, "/a~1b"), "slash")
        self.assertEqual(importer._pointer_value({"01": "object-key"}, "/01"), "object-key")
        self.assertEqual(importer._pointer_value(["zero", "one"], "/1"), "one")
        for pointer in ("/a~2b", "/00", "/-", "/2"):
            with self.subTest(pointer=pointer), self.assertRaises(importer.ImportErrorDetail):
                importer._pointer_value(["zero", "one"], pointer)

    def test_xss_quote_is_inert_when_rendered(self):
        parent = base_report()
        document = proposals(parent, injection=True)
        result = importer.import_proposals(parent, document, "1" * 64)
        html = importer.renderer.render_report(result)
        self.assertIn("\\u003cimg src=x onerror=alert(1)\\u003e", html)
        self.assertNotIn("<img src=x onerror=alert(1)>", html)

    def test_cli_rejects_dangling_output_symlink_without_creating_target(self):
        parent = base_report()
        with tempfile.TemporaryDirectory(prefix="semantic-review-symlink-") as tmp:
            root = Path(tmp)
            report_path, proposal_path = root / "parent.json", root / "proposals.json"
            target_path, output_path = root / "not-created.json", root / "output.json"
            report_path.write_bytes(importer.graph.canonical_bytes(parent))
            proposal_path.write_text(json.dumps(proposals(parent)), encoding="utf-8")
            try:
                output_path.symlink_to(target_path)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"Symlink creation unavailable: {exc}")
            command = [sys.executable, str(SCRIPT), "--report", str(report_path), "--proposals", str(proposal_path),
                       "--output", str(output_path)]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target_path.exists())
            self.assertTrue(output_path.is_symlink())

    def test_locator_individual_and_total_serialized_evidence_limits(self):
        parent = base_report()
        doc = proposals(parent)
        source = parent["head"]["model"]["sources"][0]
        source["locator"] = "L" * (importer.MAX_LOCATOR_BYTES + 1)
        parent.pop("review_revision", None)
        parent["review_revision"] = importer.graph.digest(parent)
        doc["parent_review_revision"] = parent["review_revision"]
        with self.assertRaisesRegex(importer.ImportErrorDetail, "locator exceeds"):
            importer.import_proposals(parent, doc, "a" * 64)

        parent = base_report()
        doc = proposals(parent)
        old_limit = importer.MAX_TOTAL_EVIDENCE_BYTES
        importer.MAX_TOTAL_EVIDENCE_BYTES = 1
        try:
            with self.assertRaisesRegex(importer.ImportErrorDetail, "proposal evidence exceeds"):
                importer.import_proposals(parent, doc, "a" * 64)
        finally:
            importer.MAX_TOTAL_EVIDENCE_BYTES = old_limit

    def test_bounded_loader_uses_one_snapshot_and_shared_strict_json_decoder(self):
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="semantic-review-loader-") as tmp:
            path = Path(tmp) / "input.json"
            path.write_bytes(b'{"value":1.00}')
            value, raw = importer.load_json(path, 100)
            self.assertEqual(value, {"value": 1.0})
            self.assertEqual(raw, b'{"value":1.00}')
            with mock.patch.object(importer.core, "read_json", side_effect=AssertionError("must not reread")):
                value, same_raw = importer.load_json(path, 100)
                self.assertEqual(value, {"value": 1.0})
                self.assertEqual(same_raw, raw)
            for bad in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":0.123456789012345678901}'):
                path.write_bytes(bad)
                with self.subTest(bad=bad), self.assertRaises(importer.ImportErrorDetail):
                    importer.load_json(path, 100)

    def test_bounded_loader_rechecks_bytes_after_stat_before_json_parse(self):
        from types import SimpleNamespace
        from unittest import mock
        with tempfile.TemporaryDirectory(prefix="semantic-review-loader-growth-") as tmp:
            path = Path(tmp) / "input.json"
            path.write_bytes(b'{"value":"' + b"x" * 200 + b'"}')
            with mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_size=0)), \
                    mock.patch.object(importer.core, "_parse_json_text", side_effect=AssertionError("must cap before parse")):
                with self.assertRaisesRegex(importer.ImportErrorDetail, "Input exceeds"):
                    importer.load_json(path, 100)


if __name__ == "__main__":
    unittest.main()
