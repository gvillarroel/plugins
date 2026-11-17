#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Exact-source, content invalidation, budget and Git-blob regression tests."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import repository_sources as source
import repository_graph as graph


def context():
    contract = {"schema_version": "1", "id": "terms", "version": "1",
                "types": {"Concept": {}}, "relations": {}, "checks": []}
    registry = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                "nodes": [], "relations": [], "sources": [], "bindings": {}}
    policy = {"model": "configured-small-model", "prompt_version": "extract-1",
              "instructions": "Propose only source-supported definitions; abstain on identity ambiguity.",
              "max_jobs": 5, "max_input_chars": 3000}
    return contract, registry, policy


class SourcesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "knowledge.md").write_bytes(b"# Terms\r\n\r\nA service has an owner.\r\nAn owner is a team.\r\n")

    def tearDown(self):
        self.temp.cleanup()

    def inventory(self):
        return source.inventory(self.root, ["knowledge.md"])

    def test_exact_line_spans_and_repeated_passages(self):
        value = self.inventory()
        source.verify_inventory(value)
        for item in value["sources"]:
            lines = value["documents"][0]["text"].splitlines(keepends=True)
            self.assertEqual(item["text"], "".join(lines[item["start_line"] - 1:item["end_line"]]))
        (self.root / "knowledge.md").write_text("Repeat.\n\nRepeat.\n", encoding="utf-8")
        repeated = self.inventory()["sources"]
        self.assertNotEqual(repeated[0]["id"], repeated[1]["id"])

    def test_inventory_replay_is_byte_identical(self):
        self.assertEqual(source.encoded(self.inventory()), source.encoded(self.inventory()))

    def test_unicode_separators_do_not_create_github_line_numbers(self):
        (self.root / "knowledge.md").write_text("alpha\u2028beta\n\ncharlie\n", encoding="utf-8")
        value = self.inventory()
        self.assertEqual(value["sources"][1]["locator"], "knowledge.md#L3-L3")
        self.assertEqual(value["sources"][0]["text"], "alpha\u2028beta\n")

    def test_reordered_files_and_line_endings_keep_passage_identity(self):
        (self.root / "other.md").write_text("Other.\n", encoding="utf-8")
        a = source.inventory(self.root, ["other.md", "knowledge.md"])
        b = source.inventory(self.root, ["knowledge.md", "other.md"])
        self.assertEqual(a, b)
        before = self.inventory()
        (self.root / "knowledge.md").write_bytes(before["documents"][0]["text"].encode("utf-8"))
        after = self.inventory()
        self.assertEqual(before["sources"], after["sources"])
        self.assertNotEqual(before["documents"][0]["blob_sha256"], after["documents"][0]["blob_sha256"])

    def test_blank_line_insertion_keeps_identity_but_refreshes_locator(self):
        before = self.inventory()
        (self.root / "knowledge.md").write_text("\n\n" + before["documents"][0]["text"], encoding="utf-8")
        after = self.inventory()
        self.assertEqual([x["id"] for x in before["sources"]], [x["id"] for x in after["sources"]])
        self.assertNotEqual(before["sources"][0]["locator"], after["sources"][0]["locator"])

    def test_tampered_span_rejected_even_with_recomputed_manifest_hash(self):
        value = self.inventory()
        value["sources"][0]["text"] = "Invented quote."
        value["inventory_sha256"] = source.digest({k: v for k, v in value.items() if k != "inventory_sha256"})
        with self.assertRaises(source.EngineError):
            source.verify_inventory(value)

    def test_cache_replays_proposals_and_context_changes_invalidate(self):
        contract, registry, policy = context()
        first = source.plan(self.inventory(), contract, registry, policy)
        entries = [{"request_sha256": job["request_sha256"], "response": {"abstain": True},
                    "response_sha256": source.digest({"abstain": True})} for job in first["jobs"]]
        replay = source.plan(self.inventory(), contract, registry, policy, {"entries": entries})
        self.assertEqual(replay["summary"]["model_jobs"], 0)
        self.assertEqual(replay["jobs"][0]["status"], "replay_candidate")
        for changed in ("contract", "registry", "policy"):
            c, r, p = copy.deepcopy((contract, registry, policy))
            {"contract": c, "registry": r, "policy": p}[changed]["version_note"] = "changed"
            # Contract unknown keys are rejected; a legitimate version change invalidates it.
            if changed == "contract":
                c.pop("version_note")
                c["version"] = "2"
            if changed == "registry":
                r.pop("version_note")
                r["metadata"] = {"context": "changed"}
            result = source.plan(self.inventory(), c, r, p, {"entries": entries})
            self.assertEqual(result["summary"]["cache_hits"], 0)

    def test_corrupt_cache_cannot_replay(self):
        c, r, p = context()
        with self.assertRaises(source.EngineError):
            source.plan(self.inventory(), c, r, p, {"entries": [{"request_sha256": "x", "response": {}, "response_sha256": "wrong"}]})

    def test_unchanged_pronoun_passage_invalidates_when_document_context_changes(self):
        c, r, p = context()
        document = self.root / "knowledge.md"
        document.write_text("The next paragraph concerns admins.\n\nThey must use MFA.\n", encoding="utf-8")
        before = source.plan(self.inventory(), c, r, p)
        response = {"subject": "admins", "requires": "MFA"}
        cache = {"entries": [{"request_sha256": job["request_sha256"], "response": response,
                              "response_sha256": source.digest(response)} for job in before["jobs"]]}
        document.write_text("The next paragraph concerns guests.\n\nThey must use MFA.\n", encoding="utf-8")
        after = source.plan(self.inventory(), c, r, p, cache)
        self.assertEqual(before["jobs"][1]["source_id"], after["jobs"][1]["source_id"])
        self.assertEqual(after["summary"]["cache_hits"], 0)

    def test_budget_reports_no_model_execution(self):
        c, r, p = context()
        p["max_jobs"] = 0
        result = source.plan(self.inventory(), c, r, p)
        self.assertFalse(result["summary"]["within_budget"])
        self.assertEqual(result["semantic_status"], "not_run")

    def test_exact_check_and_coverage_are_distinct(self):
        value = self.inventory()
        report = source.check_sources(value, {"sources": [value["sources"][0]]})
        self.assertEqual(report["source_status"], "valid")
        self.assertTrue(report["unrepresented_passage_ids"])
        model = {"sources": copy.deepcopy(value["sources"])}
        model["sources"][0]["text"] = "Invented."
        report = source.check_sources(value, model)
        self.assertEqual(report["source_status"], "invalid")
        self.assertEqual(report["errors"][0]["code"], "SOURCE_SPAN_MISMATCH")

    def test_path_escape_and_long_line_are_rejected(self):
        for name in ("../file.md", "C:/file.md", "sub\\file.md", "/file.md", "./file.md"):
            with self.subTest(name=name), self.assertRaises(source.EngineError):
                source.inventory(self.root, [name])
        with self.assertRaises(source.EngineError):
            source.inventory(self.root, ["knowledge.md"], max_chars=5)

    def test_write_never_overwrites_or_aliases(self):
        target = self.root / "result.json"
        source.write_new(target, {}, [])
        with self.assertRaises(FileExistsError):
            source.write_new(target, {"changed": True}, [])
        with self.assertRaises(source.EngineError):
            source.write_new(self.root / "knowledge.md", {}, [self.root / "knowledge.md"])

    def test_git_ref_reads_committed_blob_not_dirty_worktree(self):
        def run(*args):
            result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
        run("init", "-q")
        run("add", "knowledge.md")
        run("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=NUL",
            "commit", "-qm", "fixture")
        committed = source.inventory(self.root, ["knowledge.md"], ref="HEAD")
        (self.root / "knowledge.md").write_text("Dirty unrelated working copy.\n", encoding="utf-8")
        replay = source.inventory(self.root, ["knowledge.md"], ref=committed["revision"])
        self.assertEqual(committed, replay)
        self.assertNotIn("Dirty", replay["documents"][0]["text"])
        (self.root / "nested").mkdir()
        with self.assertRaises(source.EngineError) as raised:
            source.inventory(self.root / "nested", ["knowledge.md"], ref="HEAD")
        self.assertEqual(raised.exception.code, "GIT_ROOT_MISMATCH")

    def test_cli_failure_has_structured_engine_status(self):
        result = subprocess.run([sys.executable, str(Path(source.__file__)), "inventory", "--root", str(self.root),
                                 "--files", "../secret", "--output", str(self.root / "out.json")],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["engine_status"], "error")
        self.assertFalse((self.root / "out.json").exists())

    def test_assemble_resolves_quotes_without_copying_long_source_ids(self):
        value = self.inventory()
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "service", "type": "Concept", "label": "Service", "definition": "A service.",
                            "evidence": [{"quote": "A service has an owner."}]}], "relations": []}
        model = source.assemble(value, draft)
        passage = next(item for item in value["sources"] if "A service" in item["text"])
        self.assertEqual(model["nodes"][0]["source_ids"], [passage["id"]])
        self.assertEqual(model["sources"][0]["proposed_support"][0]["quote"], "A service has an owner.")
        self.assertEqual(source.check_sources(value, model)["source_status"], "valid")
        self.assertEqual(model["sources"][0]["proposed_support"][0]["status"], "support_not_reviewed")
        self.assertEqual(source.encoded(model), source.encoded(source.assemble(value, draft)))
        self.assertNotIn("proposed_support", value["sources"][1])

    def test_assemble_rejects_invented_or_ambiguous_quotations(self):
        (self.root / "knowledge.md").write_text("Repeated.\n\nRepeated.\n", encoding="utf-8")
        value = self.inventory()
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "term", "evidence": [{"quote": "Repeated."}]}], "relations": []}
        with self.assertRaises(source.EngineError):
            source.assemble(value, draft)
        draft["nodes"][0]["evidence"][0]["locator"] = value["sources"][0]["locator"]
        self.assertEqual(len(source.assemble(value, draft)["sources"]), 1)
        draft["nodes"][0]["evidence"][0]["quote"] = "Fabricated text."
        with self.assertRaises(source.EngineError):
            source.assemble(value, draft)

    def test_assemble_requires_record_specific_evidence_not_reused_ids(self):
        draft = {"schema_version": "1", "nodes": [{"id": "term", "source_ids": ["old-id"]}], "relations": []}
        with self.assertRaises(source.EngineError):
            source.assemble(self.inventory(), draft)

    def test_catalog_resolves_exact_markdown_without_model_transcription(self):
        value = self.inventory()
        catalog = source.reference_catalog(value, "base")
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "term", "type": "Concept", "label": "Term", "definition": "A term.",
                            "evidence": [{"ref": catalog["passages"][0]["ref"]}]}], "relations": []}
        model = source.assemble(value, draft, catalog)
        self.assertEqual(model["sources"][0]["text"], value["sources"][0]["text"])
        self.assertEqual(model["nodes"][0]["source_ids"], [value["sources"][0]["id"]])
        self.assertEqual(source.reference_catalog(value, "base"), catalog)

    def test_catalog_rejects_stale_inventory_or_modified_passage(self):
        value = self.inventory()
        catalog = source.reference_catalog(value, "head")
        catalog["passages"][0]["text"] = "Fabricated quote."
        with self.assertRaises(source.EngineError) as raised:
            source.assemble(value, {"nodes": [], "relations": []}, catalog)
        self.assertEqual(raised.exception.code, "STALE_CATALOG")

    def test_catalog_prefix_and_reference_scope_are_enforced(self):
        value = self.inventory()
        for invalid in (None, "../base", "Base", "", "x" * 25):
            with self.subTest(prefix=invalid), self.assertRaises(source.EngineError):
                source.reference_catalog(value, invalid)
        draft = {"nodes": [{"id": "term", "evidence": [{"ref": "base-0001"}]}], "relations": []}
        with self.assertRaises(source.EngineError):
            source.assemble(value, draft, source.reference_catalog(value, "head"))
        with self.assertRaises(source.EngineError):
            source.assemble(value, draft)

    def test_catalog_cli_writes_exact_output_without_dumping_sources(self):
        inventory_path = self.root / "inventory.json"
        inventory_path.write_bytes(source.encoded(self.inventory()))
        output = self.root / "catalog.json"
        result = subprocess.run([sys.executable, str(Path(source.__file__)), "catalog", "--inventory", str(inventory_path),
                                 "--prefix", "head", "--output", str(output)], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        catalog = json.loads(output.read_text(encoding="utf-8"))
        self.assertTrue(catalog["passages"][0]["ref"].startswith("head-"))
        self.assertNotIn("passages", json.loads(result.stdout))
        self.assertNotIn("A service has an owner", result.stdout)

    def test_change_map_reports_path_addition_and_removal_with_short_refs(self):
        base_root, head_root = self.root / "base", self.root / "head"
        base_root.mkdir()
        head_root.mkdir()
        (base_root / "retired.md").write_text("Retired definition.\n", encoding="utf-8")
        (head_root / "new.md").write_text("New definition.\n", encoding="utf-8")
        base = source.inventory(base_root, ["retired.md"])
        head = source.inventory(head_root, ["new.md"])

        report = source.inventory_changes(base, head)

        self.assertEqual([(item["kind"], item["path"]) for item in report["groups"]],
                         [("added", "new.md"), ("removed", "retired.md")])
        self.assertTrue(report["groups"][0]["head_refs"][0].startswith("head-"))
        self.assertTrue(report["groups"][1]["base_refs"][0].startswith("base-"))
        self.assertEqual(report["counts"], {"added": 1, "removed": 1, "replaced": 0, "unchanged": 0})

    def test_change_map_preserves_duplicate_occurrences_and_unchanged_context(self):
        base_root, head_root = self.root / "base", self.root / "head"
        base_root.mkdir()
        head_root.mkdir()
        before = "Repeated passage.\n\nRepeated passage.\n\nOld requirement.\n\nStable context.\n"
        after = "Repeated passage.\n\nRepeated passage.\n\nNew requirement.\n\nStable context.\n"
        (base_root / "guide.md").write_text(before, encoding="utf-8")
        (head_root / "guide.md").write_text(after, encoding="utf-8")

        report = source.inventory_changes(source.inventory(base_root, ["guide.md"]),
                                          source.inventory(head_root, ["guide.md"]))

        self.assertEqual(len(report["groups"]), 1)
        self.assertEqual(report["groups"][0]["kind"], "replaced")
        self.assertEqual(report["groups"][0]["id"], "change-0001")
        self.assertEqual(len(report["groups"][0]["fingerprint_sha256"]), 64)
        self.assertEqual(report["counts"]["unchanged"], 3)
        repeated_pairs = [pair for pair in report["unchanged"]
                          if pair["base_ref"].endswith(("0001", "0002"))]
        self.assertEqual(len(repeated_pairs), 2)
        self.assertNotEqual(repeated_pairs[0]["base_ref"], repeated_pairs[1]["base_ref"])
        self.assertEqual(report["base_inventory_sha256"], source.verify_inventory(
            source.inventory(base_root, ["guide.md"]))["inventory_sha256"])

    def test_change_map_deterministic_and_reports_whitespace_only_text_edit(self):
        base_root, head_root = self.root / "base", self.root / "head"
        base_root.mkdir()
        head_root.mkdir()
        (base_root / "rule.md").write_text("A rule.\n\nContext stays.\n", encoding="utf-8")
        (head_root / "rule.md").write_text("A  rule.\n\nContext stays.\n", encoding="utf-8")
        base = source.inventory(base_root, ["rule.md"])
        head = source.inventory(head_root, ["rule.md"])

        first = source.inventory_changes(base, head)
        second = source.inventory_changes(base, head)

        self.assertEqual(source.encoded(first), source.encoded(second))
        self.assertEqual(first["groups"][0]["kind"], "replaced")
        self.assertEqual(first["counts"]["unchanged"], 1)
        self.assertEqual(first["tool"], "repository-source-changes")

    def test_change_map_cli_is_repeatable_and_rejects_output_alias(self):
        base = self.root / "base.json"
        head = self.root / "head.json"
        base.write_bytes(source.encoded(self.inventory()))
        head.write_bytes(source.encoded(self.inventory()))
        output = self.root / "changes.json"
        args = [sys.executable, str(Path(source.__file__)), "changes", "--base-inventory", str(base),
                "--head-inventory", str(head), "--output", str(output)]
        first = subprocess.run(args, capture_output=True, text=True, check=False)
        first_bytes = output.read_bytes()
        second_output = self.root / "changes-second.json"
        second_args = [*args[:-1], str(second_output)]
        second = subprocess.run(second_args, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertEqual(second.returncode, 0, second.stdout)
        self.assertEqual(first_bytes, second_output.read_bytes())
        alias = subprocess.run([sys.executable, str(Path(source.__file__)), "changes", "--base-inventory", str(base),
                                "--head-inventory", str(head), "--output", str(base)],
                               capture_output=True, text=True, check=False)
        self.assertEqual(alias.returncode, 2)

    def test_bind_distinguishes_git_revisions_without_changing_graph(self):
        def run(*args):
            result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.decode("utf-8").strip()

        raw = b"A service has an owner.\r\n\r\nAn owner is a team.\r\n"
        (self.root / "knowledge.md").write_bytes(raw)
        run("init", "-q")
        run("config", "user.name", "Fixture")
        run("config", "user.email", "fixture@example.invalid")
        run("add", "knowledge.md")
        run("commit", "-qm", "first identical source")
        revision_one = run("rev-parse", "HEAD")
        run("commit", "--allow-empty", "-qm", "second commit with identical selected source")
        revision_two = run("rev-parse", "HEAD")
        first_inventory = source.inventory(self.root, ["knowledge.md"], ref=revision_one)
        second_inventory = source.inventory(self.root, ["knowledge.md"], ref=revision_two)
        self.assertEqual(first_inventory["documents"][0]["blob_sha256"],
                         second_inventory["documents"][0]["blob_sha256"])
        self.assertNotEqual(first_inventory["revision"], second_inventory["revision"])

        passage = first_inventory["sources"][0]
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "metadata": {"preserve": {"raw": ["caller", "metadata"]}},
                 "nodes": [{"id": "service", "type": "Concept", "label": "Service",
                            "definition": "A service.", "evidence": [{"quote": "A service has an owner.",
                                                                            "locator": passage["locator"]}]}],
                 "relations": []}
        first_model = source.assemble(first_inventory, draft)
        second_model = source.assemble(second_inventory, draft)
        first_snapshot = graph.build_snapshot(first_model, context()[0])
        second_snapshot = graph.build_snapshot(second_model, context()[0])
        before = graph.compare_models(first_model, second_model, context()[0])
        self.assertEqual(source.digest(first_model), source.digest(second_model))
        self.assertEqual(first_snapshot["graph_sha256"], second_snapshot["graph_sha256"])
        self.assertEqual(before["review_revision"], graph.compare_models(
            source.assemble(first_inventory, draft), source.assemble(second_inventory, draft),
            context()[0])["review_revision"])

        first_bound = source.bind_provenance(first_inventory, first_model)
        second_bound = source.bind_provenance(second_inventory, second_model)
        self.assertNotEqual(source.digest(first_bound), source.digest(second_bound))
        self.assertEqual(graph.build_snapshot(first_bound, context()[0])["graph_sha256"],
                         graph.build_snapshot(second_bound, context()[0])["graph_sha256"])
        bound_review = graph.compare_models(first_bound, second_bound, context()[0])
        self.assertNotEqual(before["review_revision"], bound_review["review_revision"])
        self.assertEqual(first_bound["metadata"]["preserve"], draft["metadata"]["preserve"])
        self.assertEqual(first_bound["sources"], first_model["sources"])
        self.assertEqual(first_bound["metadata"]["repository_sources"]["revision"], revision_one)
        self.assertEqual(second_bound["metadata"]["repository_sources"]["revision"], revision_two)
        descriptor = first_bound["metadata"]["repository_sources"]["documents"][0]
        self.assertEqual(descriptor["blob_sha256"], first_inventory["documents"][0]["blob_sha256"])
        self.assertEqual(descriptor["content_sha256"], first_inventory["documents"][0]["content_sha256"])
        self.assertNotEqual(descriptor["blob_sha256"], descriptor["content_sha256"])
        self.assertEqual(descriptor["blob_sha256"], source.bytes_hash(raw))
        self.assertEqual(source.bind_provenance(first_inventory, first_bound), first_bound)
        self.assertEqual(first_bound["metadata"]["repository_sources"]["authenticity"], "not_authenticated")

    def test_bind_records_opaque_origin_digest_and_preserves_content(self):
        value = self.inventory()
        passage = next(item for item in value["sources"] if "A service has an owner." in item["text"])
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "service", "type": "Concept", "label": "Service",
                            "definition": "A service.", "evidence": [{"quote": "A service has an owner.",
                                                                            "locator": passage["locator"]}]}],
                 "relations": []}
        model = source.assemble(value, draft)
        origin_one = {"source": "release-api", "version": "1.0", "capture_id": "capture-a"}
        origin_two = {"source": "release-api", "version": "2.0", "capture_id": "capture-b"}
        bound_one = source.bind_provenance(value, model, origin_one)
        bound_two = source.bind_provenance(value, model, origin_two)
        record = bound_one["metadata"]["repository_sources"]
        self.assertEqual(record["origin"]["value"], origin_one)
        self.assertEqual(record["origin"]["sha256"], source.digest(origin_one))
        self.assertEqual(record["origin"]["authenticity"], "not_authenticated")
        self.assertNotEqual(source.digest(bound_one), source.digest(bound_two))
        self.assertEqual(graph.graph_projection(bound_one), graph.graph_projection(bound_two))
        self.assertEqual(model["sources"], bound_one["sources"])
        self.assertNotIn("repository_sources", model.get("metadata", {}))

    def test_bind_rejects_stale_unknown_and_conflicting_sources(self):
        value = self.inventory()
        passage = next(item for item in value["sources"] if "A service has an owner." in item["text"])
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "service", "type": "Concept", "label": "Service",
                            "definition": "A service.", "evidence": [{"quote": "A service has an owner.",
                                                                            "locator": passage["locator"]}]}],
                 "relations": []}
        model = source.assemble(value, draft)
        stale = copy.deepcopy(model)
        stale["sources"][0]["text"] = "A changed passage."
        with self.assertRaises(source.EngineError) as raised:
            source.bind_provenance(value, stale)
        self.assertEqual(raised.exception.code, "SOURCE_SPAN_MISMATCH")

        unknown = copy.deepcopy(model)
        unknown["sources"][0]["id"] = "unrecorded-source"
        with self.assertRaises(source.EngineError) as raised:
            source.bind_provenance(value, unknown)
        self.assertEqual(raised.exception.code, "UNPINNED_SOURCE")

        dangling = copy.deepcopy(model)
        dangling["nodes"][0]["source_ids"] = ["unrecorded-source"]
        with self.assertRaises(source.EngineError) as raised:
            source.bind_provenance(value, dangling)
        self.assertEqual(raised.exception.code, "UNPINNED_SOURCE")

        collision = copy.deepcopy(model)
        collision["metadata"] = {"repository_sources": {"inventory_sha256": "other"}}
        with self.assertRaises(source.EngineError) as raised:
            source.bind_provenance(value, collision)
        self.assertEqual(raised.exception.code, "PROVENANCE_CONFLICT")

    def test_bind_rejects_nonobject_or_nonfinite_origin(self):
        value = self.inventory()
        model = {"sources": []}
        for origin in ([], "release-v1", {"version": float("nan")}, {"version": float("inf")},
                       {"nested": {7: "must not be coerced to a JSON object key"}}):
            with self.subTest(origin=origin), self.assertRaises(source.EngineError) as raised:
                source.bind_provenance(value, model, origin)
            self.assertEqual(raised.exception.code, "INVALID_ORIGIN")

    def test_source_check_rejects_conflicting_optional_identity_fields(self):
        value = self.inventory()
        original = value["sources"][0]
        for field, replacement in (("path", "other.md"), ("start_line", True),
                                   ("end_line", 999), ("document_sha256", "0" * 64),
                                   ("passage_sha256", "0" * 64)):
            with self.subTest(field=field):
                model = {"sources": [{**original, field: replacement}]}
                self.assertEqual(source.check_sources(value, model)["source_status"], "invalid")
                with self.assertRaises(source.EngineError) as raised:
                    source.bind_provenance(value, model)
                self.assertEqual(raised.exception.code, "SOURCE_SPAN_MISMATCH")
        # A portable minimal record and unrelated additional JSON metadata are
        # still valid; the helper does not require an inventory-shaped model.
        minimal = {key: original[key] for key in ("id", "text", "locator")}
        minimal["review_note"] = {"status": "unreviewed"}
        bound = source.bind_provenance(value, {"sources": [minimal]})
        self.assertEqual(bound["sources"], [minimal])

    def test_inventory_rejects_rehashed_boolean_or_float_line_positions(self):
        original = self.inventory()
        for position in (True, 1.0):
            value = copy.deepcopy(original)
            value["sources"][0]["start_line"] = position
            value["inventory_sha256"] = source.digest({key: item for key, item in value.items()
                                                       if key != "inventory_sha256"})
            with self.subTest(position=position), self.assertRaises(source.EngineError) as raised:
                source.verify_inventory(value)
            self.assertEqual(raised.exception.code, "STALE_INVENTORY")

    def test_bind_rejects_non_json_models_without_requiring_semantic_validity(self):
        value = self.inventory()
        cyclic = {}
        cyclic["cycle"] = cyclic
        for metadata in ({"x": float("nan")}, {"x": float("inf")}, {7: "value"},
                         {"tuple": (1, 2)}, cyclic):
            with self.subTest(keys=list(metadata)), self.assertRaises(source.EngineError) as raised:
                source.bind_provenance(value, {"sources": [], "metadata": metadata})
            self.assertEqual(raised.exception.code, "INVALID_MODEL")
        # Missing domain headers/types are outside this source-binding check.
        self.assertIn("repository_sources", source.bind_provenance(value, {"sources": []})["metadata"])

    def test_bind_rejects_cyclic_origins_but_allows_shared_json_children(self):
        value = self.inventory()
        cyclic_dict = {}
        cyclic_dict["cycle"] = cyclic_dict
        cyclic_list = []
        cyclic_list.append(cyclic_list)
        for origin in (cyclic_dict, {"cycle": cyclic_list}):
            with self.assertRaises(source.EngineError) as raised:
                source.bind_provenance(value, {"sources": []}, origin)
            self.assertEqual(raised.exception.code, "INVALID_ORIGIN")
        shared = {"release": "one"}
        origin = {"first": shared, "second": shared}
        bound = source.bind_provenance(value, {"sources": []}, origin)
        self.assertEqual(bound["metadata"]["repository_sources"]["origin"]["value"], origin)

    def test_existing_binding_requires_type_exact_json_even_with_matching_digest(self):
        value = self.inventory()
        origin = {"release": 1}
        bound = source.bind_provenance(value, {"sources": []}, origin)
        # Preserve the stored digest to ensure comparison does not use Python's
        # True == 1 shortcut on an inconsistent pre-existing binding value.
        bound["metadata"]["repository_sources"]["origin"]["value"]["release"] = True
        with self.assertRaises(source.EngineError) as raised:
            source.bind_provenance(value, bound, origin)
        self.assertEqual(raised.exception.code, "PROVENANCE_CONFLICT")

    def test_bind_rejects_malformed_rehashed_document_metadata(self):
        valid = self.inventory()
        model = {"sources": []}
        invalid_cases = []
        missing_raw_hash = copy.deepcopy(valid)
        del missing_raw_hash["documents"][0]["blob_sha256"]
        missing_raw_hash["inventory_sha256"] = source.digest(
            {key: item for key, item in missing_raw_hash.items() if key != "inventory_sha256"})
        invalid_cases.append(("missing blob_sha256", missing_raw_hash))
        malformed_content_hash = copy.deepcopy(valid)
        malformed_content_hash["documents"][0]["content_sha256"] = "not-a-sha256"
        malformed_content_hash["inventory_sha256"] = source.digest(
            {key: item for key, item in malformed_content_hash.items() if key != "inventory_sha256"})
        invalid_cases.append(("malformed content_sha256", malformed_content_hash))
        malformed_revision = copy.deepcopy(valid)
        malformed_revision["revision"] = "not-a-git-object-id"
        malformed_revision["inventory_sha256"] = source.digest(
            {key: item for key, item in malformed_revision.items() if key != "inventory_sha256"})
        invalid_cases.append(("malformed revision", malformed_revision))
        for label, inventory in invalid_cases:
            with self.subTest(label=label), self.assertRaises(source.EngineError) as raised:
                source.bind_provenance(inventory, model)
            self.assertEqual(raised.exception.code, "INVALID_SOURCE_METADATA")

    def test_bind_cli_writes_opt_in_binding_and_reports_invalid_origin(self):
        value = self.inventory()
        passage = next(item for item in value["sources"] if "A service has an owner." in item["text"])
        draft = {"schema_version": "1", "contract_id": "terms", "contract_version": "1",
                 "nodes": [{"id": "service", "type": "Concept", "label": "Service",
                            "definition": "A service.", "evidence": [{"quote": "A service has an owner.",
                                                                            "locator": passage["locator"]}]}],
                 "relations": []}
        inventory_path, model_path = self.root / "inventory.json", self.root / "model.json"
        inventory_path.write_bytes(source.encoded(value))
        model_path.write_bytes(source.encoded(source.assemble(value, draft)))
        origin_path = self.root / "origin.json"
        origin_path.write_text('{"capture":"trusted-acquirer-v1"}', encoding="utf-8")
        output = self.root / "bound.json"
        args = [sys.executable, str(Path(source.__file__)), "bind", "--inventory", str(inventory_path),
                "--model", str(model_path), "--origin", str(origin_path), "--output", str(output)]
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("trusted-acquirer-v1", result.stdout)
        bound = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(bound["metadata"]["repository_sources"]["origin"]["value"]["capture"],
                         "trusted-acquirer-v1")

        invalid_origin = self.root / "invalid-origin.json"
        invalid_origin.write_text('["not", "an object"]', encoding="utf-8")
        rejected = subprocess.run([*args[:-2], "--origin", str(invalid_origin), "--output",
                                   str(self.root / "rejected.json")], capture_output=True, text=True, check=False)
        self.assertEqual(rejected.returncode, 2)
        self.assertEqual(json.loads(rejected.stdout)["errors"][0]["code"], "INVALID_ORIGIN")
        self.assertFalse((self.root / "rejected.json").exists())

        malformed_inventory = copy.deepcopy(value)
        del malformed_inventory["documents"][0]["blob_sha256"]
        malformed_inventory["inventory_sha256"] = source.digest(
            {key: item for key, item in malformed_inventory.items() if key != "inventory_sha256"})
        malformed_path = self.root / "malformed-inventory.json"
        malformed_path.write_bytes(source.encoded(malformed_inventory))
        malformed_output = self.root / "malformed-output.json"
        malformed_result = subprocess.run([sys.executable, str(Path(source.__file__)), "bind", "--inventory",
                                           str(malformed_path), "--model", str(model_path), "--output",
                                           str(malformed_output)], capture_output=True, text=True, check=False)
        self.assertEqual(malformed_result.returncode, 2)
        self.assertEqual(json.loads(malformed_result.stdout)["errors"][0]["code"], "INVALID_SOURCE_METADATA")
        self.assertFalse(malformed_output.exists())


if __name__ == "__main__":
    unittest.main()
