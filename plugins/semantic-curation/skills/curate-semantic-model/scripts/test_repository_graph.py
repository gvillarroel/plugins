#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Behavioral checks for immutable snapshots, semantic changes and historical policy.

Run with uv run --script test_repository_graph.py. All generated inputs and
outputs use TemporaryDirectory; no service, model call or repository mutation.
"""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import repository_graph as graph
import semantic_model as core

SCRIPT = Path(__file__).with_name("repository_graph.py")


def fixture():
    contract = {
        "schema_version": "1", "id": "repository-demo", "version": "1",
        "types": {"Concept": {"attributes": {"rank": {"type": "number"}, "steps": {"type": "array"}}}},
        "relations": {"broader": {"from_types": ["Concept"], "to_types": ["Concept"], "acyclic": True}},
        "require_source_bindings": True,
        "checks": [{"id": "A-parent", "query": {"op": "neighbors", "from": "A", "relation": "broader"}, "expect": ["B"]}],
    }
    model = {
        "schema_version": "1", "contract_id": "repository-demo", "contract_version": "1",
        "sources": [{"id": "s1", "locator": "guide.md#first", "text": "A is a specialization of B."},
                    {"id": "s2", "locator": "guide.md#second", "text": "B names the broader concept."}],
        "nodes": [{"id": "A", "type": "Concept", "label": "First concept", "definition": "A scoped specialization.", "source_ids": ["s2", "s1"], "aliases": ["Specific", "A"], "attributes": {"rank": 1, "steps": ["first", "second"]}},
                  {"id": "B", "type": "Concept", "label": "Second concept", "definition": "The broader concept.", "source_ids": ["s2"]}],
        "relations": [{"id": "A-B", "type": "broader", "from": "A", "to": "B", "source_ids": ["s2", "s1"]}],
        "bindings": {"s2": ["B", "A"], "s1": ["A"]},
        "metadata": {"ordered": ["one", "two"]}, "history": [{"operation": "first"}, {"operation": "second"}],
    }
    return model, contract


def reverse_mappings(value):
    if isinstance(value, dict):
        return {key: reverse_mappings(item) for key, item in reversed(list(value.items()))}
    if isinstance(value, list):
        return [reverse_mappings(item) for item in value]
    return value


class SnapshotTests(unittest.TestCase):
    def test_node_reference_type_order_is_canonical_without_mutating_policy(self):
        model,contract=fixture()
        contract["types"]["Other"]={"attributes":{}}
        contract["types"]["Concept"]["attributes"]["target"]={
            "type":"string","node_reference_types":["Other","Concept"]}
        model["nodes"][0]["attributes"]["target"]="B"
        alternate=copy.deepcopy(contract)
        alternate["types"]["Concept"]["attributes"]["target"]["node_reference_types"].reverse()
        saved=copy.deepcopy(contract)
        first=graph.build_snapshot(model,contract)
        second=graph.build_snapshot(model,alternate)
        self.assertEqual(first["validation"]["contract_status"],"valid")
        self.assertEqual(graph.canonical_bytes(first),graph.canonical_bytes(second))
        self.assertEqual(contract,saved)
        contract["types"]["Concept"]["attributes"]["target"]["node_reference_types"].append("Concept")
        normalized=graph.canonical_contract(contract)
        self.assertEqual(normalized["types"]["Concept"]["attributes"]["target"]["node_reference_types"],
                         ["Concept","Concept","Other"])

    def test_repeated_snapshot_and_input_permutations_have_identical_bytes(self):
        model, contract = fixture()
        reordered = reverse_mappings(model)
        for field in ("sources", "nodes", "relations"):
            reordered[field].reverse()
        for record in reordered["nodes"] + reordered["relations"]:
            record["source_ids"].reverse()
            if "aliases" in record:
                record["aliases"].reverse()
        for values in reordered["bindings"].values():
            values.reverse()
        first = graph.build_snapshot(model, contract)
        self.assertEqual(first["validation"]["contract_status"], "valid")
        self.assertEqual(graph.canonical_bytes(first), graph.canonical_bytes(graph.build_snapshot(reordered, reverse_mappings(contract))))
        self.assertEqual(graph.canonical_bytes(first), graph.canonical_bytes(graph.build_snapshot(model, contract)))

    def test_model_and_contract_are_not_mutated(self):
        model, contract = fixture()
        originals = copy.deepcopy((model, contract))
        graph.build_snapshot(model, contract)
        graph.compare_models(model, model, contract)
        self.assertEqual((model, contract), originals)

    def test_evidence_only_change_preserves_content_graph_digest(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["sources"][0]["text"] = "The wording was clarified."
        head["sources"][0]["locator"] = "renamed.md#first"
        before, after = graph.build_snapshot(model, contract), graph.build_snapshot(head, contract)
        self.assertEqual(before["graph_sha256"], after["graph_sha256"])
        self.assertNotEqual(before["model_sha256"], after["model_sha256"])

    def test_relation_review_does_not_change_content_digest(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["relations"][0]["review"] = {"decision": "accepted", "reviewer": "reviewer", "rationale": "Verified evidence."}
        self.assertEqual(graph.build_snapshot(model, contract)["graph_sha256"], graph.build_snapshot(head, contract)["graph_sha256"])
        self.assertEqual(graph.compare_models(model, head, contract)["changes"][0]["kind"], "relation_changed")

    def test_arbitrary_arrays_and_history_preserve_order(self):
        model, contract = fixture()
        snapshot = graph.build_snapshot(model, contract)
        for target in ("attributes", "metadata", "history"):
            head = copy.deepcopy(model)
            if target == "attributes":
                head["nodes"][0]["attributes"]["steps"].reverse()
            elif target == "metadata":
                head["metadata"]["ordered"].reverse()
            else:
                head["history"].reverse()
            changed = graph.build_snapshot(head, contract)
            self.assertNotEqual(snapshot["model_sha256"], changed["model_sha256"], target)
            self.assertEqual(snapshot["graph_sha256"] == changed["graph_sha256"], target != "attributes")

    def test_duplicate_provenance_is_not_repaired(self):
        model, contract = fixture()
        model["nodes"][0]["source_ids"].append("s1")
        snapshot = graph.build_snapshot(model, contract)
        self.assertEqual(snapshot["validation"]["contract_status"], "invalid")
        self.assertIn("PROVENANCE_SCOPE", {row["code"] for row in snapshot["validation"]["errors"]})
        self.assertEqual(snapshot["model"]["nodes"][0]["source_ids"].count("s1"), 2)

    def test_duplicate_identity_is_explicit_engine_error(self):
        model, contract = fixture()
        model["nodes"].append(copy.deepcopy(model["nodes"][0]))
        with self.assertRaises(core.EngineError) as error:
            graph.build_snapshot(model, contract)
        self.assertEqual(error.exception.code, "AMBIGUOUS_IDENTITY")

    def test_nonfinite_value_is_not_hashable(self):
        with self.assertRaises(core.EngineError):
            graph.canonical_bytes({"value": float("inf")})

    def test_malformed_nonidentity_fields_remain_data_findings(self):
        model, contract = fixture()
        for field, value, expected in (("aliases", ["alias", 1], "ALIASES_TYPE"),
                                       ("attributes", [], "ATTRIBUTES_TYPE"),
                                       ("source_ids", False, "PROVENANCE_TYPE"),
                                       ("definition", {"text": "nested"}, "MISSING_REQUIRED_FIELD")):
            with self.subTest(field=field):
                candidate = copy.deepcopy(model)
                candidate["nodes"][0][field] = value
                snapshot = graph.build_snapshot(candidate, contract)
                self.assertEqual(snapshot["validation"]["contract_status"], "invalid")
                self.assertIn(expected, {row["code"] for row in snapshot["validation"]["errors"]})


class ComparisonTests(unittest.TestCase):
    def test_definition_change_is_visible_and_changes_graph(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["nodes"][0]["definition"] = "A different scope."
        report = graph.compare_models(model, head, contract)
        self.assertEqual([row["kind"] for row in report["changes"]], ["definition_changed"])
        self.assertTrue(report["summary"]["graph_changed"])
        self.assertEqual(report["semantic_status"], "not_run")

    def test_rename_keeps_identity(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["nodes"][0]["label"] = "Renamed first concept"
        changes = graph.compare_models(model, head, contract)["changes"]
        self.assertEqual([(row["kind"], row["entity_id"]) for row in changes], [("node_renamed", "A")])

    def test_source_only_changes_are_distinct_from_graph_changes(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["sources"][0]["text"] = "Updated source text."
        report = graph.compare_models(model, head, contract)
        self.assertEqual([row["kind"] for row in report["changes"]], ["source_changed"])
        self.assertFalse(report["summary"]["graph_changed"])
        self.assertTrue(report["summary"]["model_changed"])

    def test_exact_json_types_are_not_coerced(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["nodes"][0]["attributes"]["rank"] = True
        report = graph.compare_models(model, head, contract)
        self.assertIn("attributes_changed", {row["kind"] for row in report["changes"]})
        self.assertIn("ATTRIBUTE_TYPE", {row["code"] for row in report["findings"]})

    def test_integer_and_float_values_are_distinct_changes(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["nodes"][0]["attributes"]["rank"] = 1.0
        report = graph.compare_models(model, head, contract)
        self.assertEqual(report["changes"][0]["kind"], "attributes_changed")
        self.assertTrue(report["summary"]["head_valid"])
        self.assertTrue(report["summary"]["graph_changed"])

    def test_signed_float_zero_changes_match_canonical_hash_and_core_validation_stays_numeric(self):
        model, contract = fixture()
        self.assertTrue(core.exact_json_equal(-0.0, 0.0))
        for before, after in ((-0.0, 0.0), (0.0, -0.0)):
            with self.subTest(before=before, after=after):
                base = copy.deepcopy(model)
                head = copy.deepcopy(model)
                base["nodes"][0]["attributes"]["rank"] = before
                head["nodes"][0]["attributes"]["rank"] = after
                report = graph.compare_models(base, head, contract)
                self.assertNotEqual(report["base"]["graph_sha256"], report["head"]["graph_sha256"])
                self.assertNotEqual(report["base"]["model_sha256"], report["head"]["model_sha256"])
                self.assertTrue(report["summary"]["base_valid"])
                self.assertTrue(report["summary"]["head_valid"])
                self.assertEqual([row["kind"] for row in report["changes"]], ["attributes_changed"])

    def test_absent_bindings_and_empty_bindings_are_distinct_audit_changes(self):
        model, contract = fixture()
        contract["require_source_bindings"] = False
        base = copy.deepcopy(model)
        head = copy.deepcopy(model)
        del base["bindings"]
        head["bindings"] = {}
        report = graph.compare_models(base, head, contract)
        self.assertEqual(report["base"]["validation"]["contract_status"], "valid")
        self.assertEqual(report["head"]["validation"]["contract_status"], "valid")
        self.assertFalse(report["summary"]["graph_changed"])
        self.assertTrue(report["summary"]["model_changed"])
        binding = next(row for row in report["changes"] if row["kind"] == "bindings_changed")
        self.assertFalse(binding["base_present"])
        self.assertTrue(binding["head_present"])
        self.assertEqual(binding["before"], binding["after"])
        self.assertEqual(binding["base_present"], False)
        self.assertEqual(binding["head_present"], True)
        fingerprint = graph.digest({key: value for key, value in binding.items()
                                    if key not in ("id", "fingerprint")})
        self.assertEqual(binding["fingerprint"], fingerprint)
        self.assertEqual(binding["id"], "change:" + fingerprint[:24])

    def test_absent_and_null_root_fields_are_directional_and_fingerprinted(self):
        model, contract = fixture()
        for field, kind in (("metadata", "metadata_changed"), ("history", "history_changed"),
                            ("custom", "model_field_changed")):
            for direction in ("base_to_head", "head_to_base"):
                with self.subTest(field=field, direction=direction):
                    base, head = copy.deepcopy(model), copy.deepcopy(model)
                    present, absent = (base, head) if direction == "base_to_head" else (head, base)
                    present[field] = None
                    absent.pop(field, None)
                    change = next(row for row in graph.compare_models(base, head, contract)["changes"]
                                  if row["kind"] == kind)
                    self.assertEqual(change["base_present"], field in base)
                    self.assertEqual(change["head_present"], field in head)
                    self.assertEqual(change["before"], change["after"])
                    fingerprint = graph.digest({key: value for key, value in change.items()
                                                if key not in ("id", "fingerprint")})
                    self.assertEqual(change["fingerprint"], fingerprint)

    def test_record_membership_changes_are_visible_for_nodes_relations_and_sources(self):
        model, contract = fixture()
        cases = (("nodes", 0, "optional_note", "node_changed"),
                 ("relations", 0, "review", "relation_changed"),
                 ("sources", 0, "media_type", "source_changed"))
        for collection, index, field, kind in cases:
            for direction in ("base_to_head", "head_to_base"):
                with self.subTest(collection=collection, direction=direction):
                    base, head = copy.deepcopy(model), copy.deepcopy(model)
                    present_side = base if direction == "base_to_head" else head
                    present_side[collection][index][field] = None
                    change = next(row for row in graph.compare_models(base, head, contract)["changes"]
                                  if row["kind"] == kind)
                    if collection == "nodes":
                        self.assertEqual(change["base_present"], direction == "base_to_head")
                        self.assertEqual(change["head_present"], direction == "head_to_base")
                        continue
                    if direction == "base_to_head":
                        self.assertIn(field, change["base_present_fields"])
                        self.assertNotIn(field, change["head_present_fields"])
                    else:
                        self.assertNotIn(field, change["base_present_fields"])
                        self.assertIn(field, change["head_present_fields"])
                    self.assertNotEqual(change["base_present_fields"], change["head_present_fields"])
                    fingerprint = graph.digest({key: value for key, value in change.items()
                                                if key not in ("id", "fingerprint")})
                    self.assertEqual(change["fingerprint"], fingerprint)

    def test_model_hash_differences_always_have_a_recorded_change(self):
        model, contract = fixture()
        variants = []
        signed_zero = copy.deepcopy(model)
        signed_zero["nodes"][0]["attributes"]["rank"] = -0.0
        signed_zero["nodes"][1]["attributes"] = {"rank": 0.0}
        variants.append(("signed-zero", signed_zero, contract))
        metadata = copy.deepcopy(model)
        metadata["metadata"]["edition"] = "second"
        variants.append(("metadata", metadata, contract))
        history = copy.deepcopy(model)
        history["history"][0]["operation"] = "changed"
        variants.append(("history", history, contract))
        source_extra = copy.deepcopy(model)
        source_extra["sources"][0]["media_type"] = "text/plain"
        variants.append(("source-extra", source_extra, contract))
        nested_array = copy.deepcopy(model)
        nested_array["nodes"][0]["attributes"]["steps"].reverse()
        variants.append(("nested-array", nested_array, contract))
        root_field = copy.deepcopy(model)
        root_field["custom"] = None
        variants.append(("root-field", root_field, contract))
        binding_contract = copy.deepcopy(contract)
        binding_contract["require_source_bindings"] = False
        absent_bindings = copy.deepcopy(model)
        del absent_bindings["bindings"]
        variants.append(("bindings-absent", absent_bindings, binding_contract))
        for label, candidate, selected_contract in variants:
            with self.subTest(label=label):
                before = graph.build_snapshot(model, selected_contract)
                after = graph.build_snapshot(candidate, selected_contract)
                report = graph.compare_models(model, candidate, selected_contract)
                self.assertNotEqual(before["model_sha256"], after["model_sha256"])
                self.assertTrue(report["changes"], label)

    def test_hash_identical_canonical_permutations_have_no_recorded_changes(self):
        model, contract = fixture()
        reordered = reverse_mappings(model)
        for field in ("sources", "nodes", "relations"):
            reordered[field].reverse()
        for row in reordered["nodes"] + reordered["relations"]:
            row["source_ids"].reverse()
            if "aliases" in row:
                row["aliases"].reverse()
        for values in reordered["bindings"].values():
            values.reverse()
        before = graph.build_snapshot(model, contract)
        after = graph.build_snapshot(reordered, contract)
        self.assertEqual(before["model_sha256"], after["model_sha256"])
        self.assertEqual(graph.compare_models(model, reordered, contract)["changes"], [])

    def test_whole_candidate_cycle_with_historical_edges_is_detected(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["relations"].append({"id": "B-A", "type": "broader", "from": "B", "to": "A", "source_ids": ["s2"]})
        report = graph.compare_models(model, head, contract)
        cycle = next(row for row in report["findings"] if row["code"] == "CYCLE_FORBIDDEN")
        self.assertEqual(cycle["classification"], "new")
        self.assertTrue(cycle["evidence"])
        self.assertFalse(report["summary"]["head_valid"])

    def test_missing_definition_keeps_invalid_candidate_for_review(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        del head["nodes"][0]["definition"]
        report = graph.compare_models(model, head, contract)
        missing = next(row for row in report["findings"] if row["code"] == "MISSING_REQUIRED_FIELD")
        self.assertEqual(missing["entity_id"], "A")
        self.assertEqual(missing["evidence"][0]["locator"], "guide.md#first")
        self.assertNotIn("definition", report["head"]["model"]["nodes"][0])
        self.assertEqual(report["competency_deltas"][0]["status"], "not_run")
        self.assertEqual(report["competency_deltas"][0]["base_status"], "completed")
        self.assertIsNone(report["competency_deltas"][0]["head_passed"])

    def test_equal_ids_in_different_collections_keep_correct_evidence(self):
        model, contract = fixture()
        model["relations"][0]["id"] = "A"
        model["relations"][0]["source_ids"] = ["s2"]
        head = copy.deepcopy(model)
        head["nodes"][0]["source_ids"] = ["s1"]
        del head["nodes"][0]["definition"]
        report = graph.compare_models(model, head, contract)
        missing = next(row for row in report["findings"] if row["code"] == "MISSING_REQUIRED_FIELD")
        self.assertEqual([row["source_id"] for row in missing["evidence"]], ["s1"])

    def test_invalid_comparison_is_invariant_under_record_and_mapping_permutations(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        del head["nodes"][0]["definition"]
        head["relations"][0]["to"] = "missing"
        before = graph.compare_models(model, head, contract)
        other_base, other_head = reverse_mappings(model), reverse_mappings(head)
        for value in (other_base, other_head):
            for collection in ("sources", "nodes", "relations"):
                value[collection].reverse()
        after = graph.compare_models(other_base, other_head, reverse_mappings(contract))
        self.assertEqual(graph.canonical_bytes(before), graph.canonical_bytes(after))

    def test_changed_root_field_is_not_silently_omitted_from_changes(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["contract_version"] = "new-version"
        report = graph.compare_models(model, head, contract)
        self.assertIn("model_field_changed", {row["kind"] for row in report["changes"]})
        self.assertIn("CONTRACT_MISMATCH", {row["code"] for row in report["findings"]})

    def test_proposed_weak_policy_cannot_erase_historical_rule_failure(self):
        model, contract = fixture()
        head, proposed = copy.deepcopy(model), copy.deepcopy(contract)
        head["relations"].append({"id": "B-A", "type": "broader", "from": "B", "to": "A", "source_ids": ["s2"]})
        proposed["relations"]["broader"]["acyclic"] = False
        report = graph.compare_models(model, head, contract, proposed)
        self.assertEqual(report["head"]["validation"]["contract_status"], "invalid")
        self.assertEqual(report["head"]["proposed_validation"]["contract_status"], "valid")
        self.assertIn("CYCLE_FORBIDDEN", {row["code"] for row in report["findings"]})
        self.assertIn("POLICY_CHANGE", {row["code"] for row in report["findings"]})
        self.assertTrue(report["summary"]["policy_changed"])

    def test_new_contract_violations_are_visible_without_replacing_historical_validation(self):
        model, contract = fixture()
        proposed = copy.deepcopy(contract)
        proposed["types"]["Concept"]["required_attributes"] = ["rank"]
        report = graph.compare_models(model, model, contract, proposed)
        self.assertTrue(report["summary"]["head_valid"])
        self.assertFalse(report["summary"]["proposed_head_valid"])
        missing = next(row for row in report["findings"] if row["code"] == "MISSING_ATTRIBUTE")
        self.assertEqual(missing["policy_scope"], "proposed")
        self.assertEqual(missing["entity_id"], "B")

    def test_historical_errors_and_resolutions_stay_visible(self):
        model, contract = fixture()
        del model["nodes"][0]["definition"]
        historical = graph.compare_models(model, model, contract)
        self.assertEqual(historical["findings"][0]["classification"], "historical")
        head = copy.deepcopy(model)
        head["nodes"][0]["definition"] = "Repaired definition."
        resolved = graph.compare_models(model, head, contract)
        self.assertEqual(resolved["findings"][0]["classification"], "resolved")
        self.assertTrue(resolved["findings"][0]["historical"])

    def test_node_removal_lists_incident_relations_and_changed_competency(self):
        model, contract = fixture()
        head = copy.deepcopy(model)
        head["nodes"] = [row for row in head["nodes"] if row["id"] != "B"]
        head["relations"] = []
        head["bindings"]["s2"] = ["A"]
        report = graph.compare_models(model, head, contract)
        impact = next(row for row in report["findings"] if row["code"] == "REMOVED_NODE_IMPACT")
        self.assertEqual(impact["affected_relation_ids"], ["A-B"])
        self.assertEqual(report["competency_deltas"][0]["after"], [])
        self.assertFalse(report["competency_deltas"][0]["head_passed"])

    def test_revision_binds_evidence_and_policy(self):
        model, contract = fixture()
        baseline = graph.compare_models(model, model, contract)
        head = copy.deepcopy(model)
        head["sources"][0]["text"] = "Changed evidence."
        revised = graph.compare_models(model, head, contract)
        self.assertNotEqual(baseline["review_revision"], revised["review_revision"])
        without_revision = {key: value for key, value in revised.items() if key != "review_revision"}
        self.assertEqual(revised["review_revision"], graph.digest(without_revision))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model, self.contract = fixture()
        self.base = self.write("base.json", self.model)
        self.head = self.write("head.json", self.model)
        self.policy = self.write("contract.json", self.contract)

    def write(self, name, payload):
        path = self.root / name
        path.write_bytes(graph.canonical_bytes(payload))
        return path

    def run_cli(self, command="compare", output="report.json", env=None, extra=()):
        args = [sys.executable, "-B", str(SCRIPT), command, "--contract", str(self.policy), "--output", str(self.root / output)]
        if command == "compare":
            args += ["--base", str(self.base), "--head", str(self.head)]
        else:
            args += ["--model", str(self.head)]
        result = subprocess.run(args + list(extra), capture_output=True, text=True, check=False, env=env)
        self.assertNotIn("Traceback", result.stderr)
        return result, json.loads(result.stdout)

    def test_cross_hash_seed_reports_are_byte_identical(self):
        outputs = []
        for seed in ("1", "777", "random"):
            env = {**os.environ, "PYTHONHASHSEED": seed}
            result, _ = self.run_cli(output=seed + ".json", env=env)
            self.assertEqual(result.returncode, 0, result.stdout)
            data = (self.root / (seed + ".json")).read_bytes()
            self.assertNotIn(b"\r", data)
            outputs.append(data)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])

    def test_invalid_snapshot_is_written_with_exit_one(self):
        del self.model["nodes"][0]["definition"]
        self.write("head.json", self.model)
        result, stdout = self.run_cli("snapshot")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(stdout["engine_status"], "completed")
        self.assertEqual(json.loads((self.root / "report.json").read_bytes())["validation"]["contract_status"], "invalid")

    def test_invalid_proposed_contract_state_returns_exit_one(self):
        proposed = copy.deepcopy(self.contract)
        proposed["types"]["Concept"]["required_attributes"] = ["rank"]
        path = self.write("proposed-contract.json", proposed)
        result, _ = self.run_cli(extra=("--head-contract", str(path)))
        self.assertEqual(result.returncode, 1)
        report = json.loads((self.root / "report.json").read_bytes())
        self.assertTrue(report["summary"]["head_valid"])
        self.assertFalse(report["summary"]["proposed_head_valid"])

    def test_inputs_and_existing_outputs_are_preserved(self):
        originals = {path: path.read_bytes() for path in (self.base, self.head, self.policy)}
        output = self.write("report.json", {"keep": "original"})
        previous = output.read_bytes()
        result, stdout = self.run_cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(stdout["errors"][0]["code"], "OUTPUT_ERROR")
        self.assertEqual(previous, output.read_bytes())
        for path, data in originals.items():
            self.assertEqual(path.read_bytes(), data)

    def test_output_cannot_alias_an_input(self):
        original = self.base.read_bytes()
        result, stdout = self.run_cli(output="base.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(stdout["errors"][0]["code"], "INPUT_OVERWRITE_FORBIDDEN")
        self.assertEqual(original, self.base.read_bytes())

    def test_output_hardlink_cannot_alias_an_input(self):
        alias = self.root / "alias.json"
        try:
            os.link(self.base, alias)
        except OSError as exc:
            self.skipTest(str(exc))
        original = self.base.read_bytes()
        result, stdout = self.run_cli(output="alias.json")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(stdout["errors"][0]["code"], "INPUT_OVERWRITE_FORBIDDEN")
        self.assertEqual(self.base.read_bytes(), original)

    def test_duplicate_keys_and_nonfinite_input_are_engine_failures(self):
        for text in ('{"nodes":[],"nodes":[]}', '{"value":NaN}', '{"value":1e999}'):
            with self.subTest(text=text):
                self.head.write_text(text, encoding="utf-8")
                result, stdout = self.run_cli()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(stdout["engine_status"], "error")
                self.assertFalse((self.root / "report.json").exists())

    def test_invalid_comparison_is_written_and_retains_original_model(self):
        self.model["relations"][0]["to"] = "missing"
        self.write("head.json", self.model)
        result, _ = self.run_cli()
        self.assertEqual(result.returncode, 1)
        report = json.loads((self.root / "report.json").read_bytes())
        self.assertIn("DANGLING_REFERENCE", {row["code"] for row in report["findings"]})
        self.assertEqual(report["head"]["model"]["relations"][0]["to"], "missing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
