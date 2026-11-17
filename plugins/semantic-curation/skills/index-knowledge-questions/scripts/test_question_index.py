#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Deterministic contract, ranking, evidence-budget, and CLI controls."""

from __future__ import annotations

from copy import deepcopy
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import question_index as qi


def fixture() -> dict:
    return {
        "schema_version": 1,
        "passages": [
            {"id": "spindle", "text": "The rotary spindle is inspected each shift.", "source": "manual.md", "locator": "L4"},
            {"id": "bearing", "text": "The rotor bearing receives lubricant weekly.", "source": "manual.md", "locator": "L9"},
            {"id": "isolation", "text": "Disconnect the supply before opening the enclosure.", "source": "safety.md", "locator": "L8"},
            {"id": "distractor", "text": "The ice cream rotor bearing display has a weekly offer.", "source": "catalog.md", "locator": "L3"},
        ],
        "concepts": [
            {"id": "machine-part", "label": "machine component", "aliases": ["mechanical parts"], "parents": []},
            {"id": "spindle", "label": "rotary spindle", "aliases": ["turning shaft"], "parents": ["machine-part"]},
            {"id": "bearing", "label": "rotor bearing", "aliases": ["rotation support"], "parents": ["machine-part"]},
            {"id": "isolation", "label": "supply disconnection", "aliases": ["power isolation"], "parents": []},
        ],
        "predicates": [{"id": "requires", "label": "requires", "aliases": ["prerequisite"]}],
        "annotations": [
            {"passage_id": "spindle", "concept_ids": ["spindle"]},
            {"passage_id": "bearing", "concept_ids": ["bearing"]},
            {"passage_id": "isolation", "concept_ids": ["isolation"]},
        ],
        "relations": [{"id": "spindle-isolation", "subject": "spindle", "predicate": "requires", "object": "isolation", "evidence": ["spindle", "isolation"]}],
        "families": [
            {"id": "part-list", "kind": "taxonomy", "cues": ["list", "which components"], "examples": ["List mechanical parts."]},
            {"id": "dependencies", "kind": "relation", "cues": ["requires", "prerequisite"], "examples": ["What requires power isolation?"]},
        ],
    }


class InputContractTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(qi.validate_input(fixture())["schema_version"], 1)

    def test_minimal_no_semantics(self):
        data = fixture()
        for key in ("concepts", "predicates", "annotations", "relations", "families"):
            data[key] = []
        self.assertEqual(len(qi.build(data)["input"]["passages"]), 4)

    def test_exact_closed_fields(self):
        for target in ("root", "passage", "concept", "relation"):
            with self.subTest(target=target):
                data = fixture()
                obj = data if target == "root" else data[{"passage": "passages", "concept": "concepts", "relation": "relations"}[target]][0]
                obj["extra"] = "unexpected"
                with self.assertRaises(qi.ContractError):
                    qi.build(data)

    def test_boolean_version_rejected(self):
        data = fixture()
        data["schema_version"] = True
        with self.assertRaises(qi.ContractError):
            qi.build(data)

    def test_empty_passages_rejected(self):
        data = fixture()
        data["passages"] = []
        with self.assertRaises(qi.ContractError):
            qi.build(data)

    def test_duplicate_identity_rejected(self):
        for name in ("passages", "concepts", "predicates", "annotations", "relations", "families"):
            with self.subTest(name=name):
                data = fixture()
                data[name].append(deepcopy(data[name][0]))
                with self.assertRaises(qi.ContractError):
                    qi.build(data)

    def test_invalid_foreign_keys(self):
        mutations = [
            ("concepts", "parents", ["missing"]),
            ("annotations", "passage_id", "missing"),
            ("annotations", "concept_ids", ["missing"]),
            ("relations", "subject", "missing"),
            ("relations", "object", "missing"),
            ("relations", "predicate", "missing"),
            ("relations", "evidence", ["missing"]),
        ]
        for name, key, value in mutations:
            with self.subTest(name=name, key=key):
                data = fixture()
                data[name][0][key] = value
                with self.assertRaises(qi.ContractError):
                    qi.build(data)

    def test_cycle_rejected(self):
        data = fixture()
        data["concepts"][0]["parents"] = ["spindle"]
        with self.assertRaises(qi.ContractError):
            qi.build(data)

    def test_diamond_taxonomy_accepted(self):
        data = fixture()
        data["concepts"].append({"id": "intermediate", "label": "intermediate", "aliases": [], "parents": ["machine-part"]})
        data["concepts"][1]["parents"].append("intermediate")
        self.assertEqual(qi.build(data)["schema_version"], 1)

    def test_repeated_alias_and_evidence_rejected(self):
        for name, key in (("concepts", "aliases"), ("relations", "evidence")):
            data = fixture()
            data[name][0][key].append(data[name][0][key][0])
            with self.assertRaises(qi.ContractError):
                qi.build(data)

    def test_empty_evidence_rejected(self):
        data = fixture()
        data["relations"][0]["evidence"] = []
        with self.assertRaises(qi.ContractError):
            qi.build(data)

    def test_wrong_types_rejected(self):
        mutations = [("concepts", "aliases", "alias"), ("passages", "text", 42), ("families", "kind", "freeform"), ("relations", "subject", []), ("annotations", "concept_ids", [5])]
        for name, key, value in mutations:
            data = fixture()
            data[name][0][key] = value
            with self.assertRaises(qi.ContractError):
                qi.build(data)


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.index = qi.build(fixture())

    def test_digest_changes_with_source(self):
        other = fixture()
        other["passages"][0]["locator"] = "L5"
        self.assertNotEqual(self.index["input_sha256"], qi.build(other)["input_sha256"])

    def test_tampering_rejected(self):
        self.index["input"]["passages"][0]["text"] += " altered"
        with self.assertRaises(qi.ContractError):
            qi.search(self.index, "spindle")

    def test_hash_is_key_order_independent(self):
        reversed_data = dict(reversed(list(fixture().items())))
        self.assertEqual(qi.build(reversed_data)["input_sha256"], self.index["input_sha256"])

    def test_alias_improves_retrieval(self):
        baseline = qi.search(self.index, "turning shaft", "lexical", 1)
        guided = qi.search(self.index, "turning shaft", "guided", 1)
        self.assertEqual(baseline["hits"], [])
        self.assertEqual(guided["hits"][0]["passage_id"], "spindle")

    def test_taxonomy_collects_children(self):
        result = qi.search(self.index, "List mechanical parts", top_k=2)
        self.assertEqual(result["family_kind"], "taxonomy")
        self.assertEqual({hit["passage_id"] for hit in result["hits"]}, {"spindle", "bearing"})

    def test_atomic_relation_evidence(self):
        result = qi.search(self.index, "What prerequisite applies to the turning shaft?", top_k=2)
        self.assertEqual({hit["passage_id"] for hit in result["hits"]}, {"spindle", "isolation"})
        self.assertTrue(result["bundles"][0]["complete"])

    def test_insufficient_budget_never_reports_complete(self):
        result = qi.search(self.index, "What prerequisite applies to the turning shaft?", top_k=1)
        self.assertEqual(len(result["hits"]), 1)
        self.assertFalse(result["bundles"][0]["complete"])
        self.assertTrue(any("cannot fit" in warning for warning in result["warnings"]))

    def test_predicate_alone_does_not_bind_relation(self):
        result = qi.search(self.index, "What prerequisite applies to nothing?", top_k=2)
        self.assertEqual(result["bundles"], [])

    def test_unrelated_query_is_not_a_support_claim(self):
        result = qi.search(self.index, "What is the spindle made of?", top_k=2)
        self.assertTrue(result["hits"])
        self.assertEqual(result["authority"], "retrieval-candidates-only")
        self.assertTrue(any("do not establish factual support" in warning for warning in result["warnings"]))

    def test_no_substring_concept_matches(self):
        self.assertFalse(qi.phrase_in("rotor", "rotors"))
        self.assertTrue(qi.phrase_in("Power isolation", "POWER—isolation is necessary"))

    def test_explicit_family_and_unknown(self):
        result = qi.search(self.index, "mechanical parts", family="part-list")
        self.assertEqual(result["family"], "part-list")
        with self.assertRaises(qi.ContractError):
            qi.search(self.index, "spindle", family="missing")

    def test_top_k_contract(self):
        for value in (0, -1, 1001, True, 1.5):
            with self.assertRaises(qi.ContractError):
                qi.search(self.index, "spindle", top_k=value)

    def test_determinism(self):
        self.assertEqual(qi.search(self.index, "spindle", top_k=3), qi.search(self.index, "spindle", top_k=3))

    def test_examples_never_introduce_evidence(self):
        data = fixture()
        data["families"][0]["examples"] = ["The secret material is zirconium."]
        result = qi.search(qi.build(data), "zirconium", top_k=3)
        self.assertEqual(result["hits"], [])


class CliTests(unittest.TestCase):
    def test_fresh_process_hashseed_invariance(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            index = Path(folder) / "index.json"
            qi.write_json(index, qi.build(fixture()))
            script = Path(qi.__file__).resolve()
            command = [sys.executable, "-B", str(script), "search", str(index), "--query", "rotary spindle inspected shift weekly rotor bearing receives lubricant", "--top-k", "4"]
            observations = []
            for seed in ("1", "2", "37"):
                result = subprocess.run(command, capture_output=True, check=True, env={**os.environ, "PYTHONHASHSEED": seed})
                observations.append(result.stdout)
            self.assertEqual(observations[0], observations[1])
            self.assertEqual(observations[1], observations[2])

    def test_duplicate_json_and_nonfinite_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder) / "bad.json"
            for value in ('{"schema_version":1,"schema_version":1}', '{"x": NaN}', '{"x": Infinity}'):
                path.write_text(value, encoding="utf-8")
                with self.assertRaises(qi.ContractError):
                    qi.read_json(path)

    def test_exact_paths_and_no_overwrites(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            root = Path(folder)
            source, index, answer = root / "input.json", root / "nested/index.json", root / "hits.json"
            source.write_text(json.dumps(fixture()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(qi.main(["build", str(source), str(index)]), 0)
                before = index.read_bytes()
                self.assertEqual(qi.main(["build", str(source), str(index)]), 2)
                self.assertEqual(index.read_bytes(), before)
                self.assertEqual(qi.main(["validate", str(index)]), 0)
                self.assertEqual(qi.main(["search", str(index), "--query", "turning shaft", "--output", str(answer)]), 0)
                self.assertEqual(qi.main(["search", str(index), "--query", "anything", "--output", str(source)]), 2)
            self.assertEqual(json.loads(answer.read_text(encoding="utf-8"))["hits"][0]["passage_id"], "spindle")
            self.assertEqual(json.loads(source.read_text(encoding="utf-8")), fixture())


if __name__ == "__main__":
    unittest.main()
