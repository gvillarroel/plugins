"""Regression cases discovered in sequential workflow review rounds R24–R33."""

import copy
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from knowledge_catalog.workflow import Workflow


class LocalTransport:
    def __init__(self):
        self.applied = 0

    def build_plan(self, metadata, entry_id=None, remote_snapshot=False):
        return {
            "project": "test-project",
            "location": "us-central1",
            "entry_id": entry_id or "dataset",
            "target": "projects/test-project/locations/us-central1/entryGroups/curated/entries/dataset",
            "snapshot": {"mode": "verified" if remote_snapshot else "unverified"},
            "metadata": copy.deepcopy(metadata),
        }

    def apply_plan(self, plan):
        self.applied += 1
        return {"status": "published", "target": plan["target"]}


@pytest.fixture
def review(tmp_path, monkeypatch):
    flow = Workflow(tmp_path / ".kc")
    flow.configure(project="test-project", allowed_projects=["test-project"])
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n2,10\n3,12\n", encoding="utf-8")
    client = LocalTransport()
    monkeypatch.setattr(flow, "client", lambda: client)
    proposal = flow.propose(str(source), provenance={"license": "MIT", "owner": "Test stewardship"})
    return flow, proposal, client, source


@pytest.mark.parametrize("operation", ["revise", "replan", "reject", "publish"])
def test_r24_stale_tab_cannot_overwrite_or_publish(review, operation):
    flow, old, client, _ = review
    flow.configure(writes_enabled=True)
    current = flow.revise(old["id"], {"title": "Fresh human title"}, expected_digest=old["digest"])
    before = len(flow.events())
    with pytest.raises(ValueError, match="Proposal changed"):
        if operation == "revise":
            flow.revise(old["id"], {"title": "Stale"}, expected_digest=old["digest"])
        elif operation == "reject":
            flow.reject(old["id"], "Stale reason", expected_digest=old["digest"])
        else:
            getattr(flow, operation)(old["id"], expected_digest=old["digest"])
    assert flow.get(old["id"]) == current
    assert len(flow.events()) == before
    assert client.applied == 0


def store(flow, proposal):
    with flow.connect() as con:
        con.execute("UPDATE proposals SET body=? WHERE id=?", (json.dumps(proposal), proposal["id"]))


@pytest.mark.parametrize("reviewer", [None, False, [], "", "x" * 201])
def test_r25_approval_rejects_invalid_reviewer_types(review, reviewer):
    flow, proposal, _, _ = review
    with pytest.raises(ValueError, match="Reviewer name"):
        flow.approve(proposal["id"], proposal["digest"], reviewer)
    assert flow.get(proposal["id"])["approval"] is None


def test_r25_tampered_draft_cannot_be_approved_using_saved_digest(review):
    flow, proposal, _, _ = review
    proposal["metadata"]["description"] = "This was changed outside the versioned review flow."
    store(flow, proposal)
    with pytest.raises(ValueError, match="integrity"):
        flow.approve(proposal["id"], proposal["digest"], "Human reviewer")


@pytest.mark.parametrize("stamp", [True, "now", None, float("nan"), float("inf"), 10**20])
def test_r25_invalid_approval_timestamps_never_reach_cloud(review, stamp):
    flow, proposal, client, _ = review
    flow.configure(writes_enabled=True)
    proposal = flow.replan(proposal["id"], live=True)
    proposal = flow.approve(proposal["id"], proposal["digest"], "Human tester")
    proposal["approval"]["at"] = stamp
    store(flow, proposal)
    with pytest.raises(ValueError, match="Invalid human approval"):
        flow.publish(proposal["id"])
    assert client.applied == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"writes_enabled": "false"},
        {"writes_enabled": 1},
        {"allowed_projects": "test-project"},
        {"allowed_projects": [False]},
        {"allowed_projects": ["test-project", "test-project"]},
        {"allowed_roots": []},
        {"allowed_roots": ["relative/path"]},
        {"approval_ttl_seconds": -1},
        {"approval_ttl_seconds": True},
        {"project": "../project"},
        {"location": "../location"},
    ],
)
def test_r26_config_schema_fails_closed_without_writing(review, updates):
    flow, _, _, _ = review
    original = flow.config_path.read_bytes()
    with pytest.raises(ValueError):
        flow.configure(**updates)
    assert flow.config_path.read_bytes() == original


def test_r26_interrupted_atomic_replace_preserves_previous_config(review, monkeypatch):
    flow, _, _, _ = review
    original = flow.config_path.read_bytes()

    def fail(*args):
        raise OSError("simulated filesystem interruption")

    monkeypatch.setattr("knowledge_catalog.workflow.os.replace", fail)
    with pytest.raises(OSError, match="interruption"):
        flow.configure(location="europe-west1")
    assert flow.config_path.read_bytes() == original
    assert not list(flow.home.glob(".config-*"))


def test_r26_manually_corrupted_config_cannot_enable_access(review):
    flow, _, _, _ = review
    flow.config_path.write_text('{"writes_enabled":"yes"}', encoding="utf-8")
    with pytest.raises(ValueError, match="boolean"):
        flow.config()


def live_approved(flow, proposal):
    flow.configure(writes_enabled=True)
    planned = flow.replan(proposal["id"], live=True)
    return flow.approve(planned["id"], planned["digest"], "Human test reviewer")


def test_r27_concurrent_publication_applies_only_once(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    entered, release = threading.Event(), threading.Event()

    def paused(plan):
        entered.set()
        assert release.wait(5)
        client.applied += 1
        return {"status": "published", "target": plan["target"]}

    monkeypatch.setattr(client, "apply_plan", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(flow.publish, proposal["id"])
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError, match="human approval"):
                flow.publish(proposal["id"])
        finally:
            release.set()
        assert first.result(timeout=5)["status"] == "published"
    assert client.applied == 1
    assert sum(event["action"] == "publishing" for event in flow.events()) == 1


def test_r27_failed_attempt_keeps_audit_and_requires_new_approval(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)

    def fail(plan):
        raise TimeoutError("request outcome unknown")

    monkeypatch.setattr(client, "apply_plan", fail)
    with pytest.raises(TimeoutError):
        flow.publish(proposal["id"])
    failed = flow.get(proposal["id"])
    assert failed["status"] == "failed" and failed["approval"] is None
    assert failed["publication"]["attempt"]
    assert failed["publication"]["finished_at"] >= failed["publication"]["started_at"]
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])


@pytest.mark.parametrize(
    "result",
    [
        None,
        {},
        {"status": "pending"},
        {"status": "published", "target": "other"},
        {"status": "unchanged", "target": "other"},
    ],
)
def test_r27_unconfirmed_transport_outcome_is_never_success(review, monkeypatch, result):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    monkeypatch.setattr(client, "apply_plan", lambda plan: result)
    with pytest.raises(ValueError, match="did not confirm"):
        flow.publish(proposal["id"])
    assert flow.get(proposal["id"])["status"] == "failed"


def test_r27_confirmed_idempotent_remote_noop_is_successful(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    monkeypatch.setattr(
        client,
        "apply_plan",
        lambda plan: {"status": "unchanged", "target": plan["target"], "operations_applied": []},
    )
    published = flow.publish(proposal["id"])
    assert published["status"] == "published"
    assert published["result"]["status"] == "unchanged"
    assert published["result"]["operations_applied"] == []
    assert published["approval"] is None


def test_r28_history_survives_restart_and_diff_identifies_semantic_edit(review):
    flow, first, _, _ = review
    second = flow.revise(first["id"], {"title": "Orders for retail fulfilment"})
    third = flow.revise(first["id"], {"owner": "New accountable owner"})
    restarted = Workflow(flow.home)
    page = restarted.history(first["id"], limit=2)
    assert [item["revision"] for item in page["revisions"]] == [3, 2]
    assert page["next_before_revision"] == 2
    last = restarted.history(first["id"], before_revision=2)
    assert [item["revision"] for item in last["revisions"]] == [1]
    assert restarted.get_revision(first["id"], 1)["metadata"]["title"] == first["metadata"]["title"]
    changes = restarted.diff(first["id"], second["revision"], third["revision"])
    assert any(
        c["path"] == "/metadata/owner" and c["after"] == "New accountable owner" for c in changes["changes"]
    )


def test_r28_approval_does_not_rewrite_revision_snapshot(review):
    flow, proposal, _, _ = review
    original = flow.get_revision(proposal["id"], proposal["revision"])
    flow.approve(proposal["id"], proposal["digest"], "Human tester")
    assert flow.get_revision(proposal["id"], proposal["revision"]) == original
    assert any(e["action"] == "approved" for e in flow.events())


def test_r28_existing_installation_migrates_current_revision_only(review):
    flow, proposal, _, _ = review
    with flow.connect() as con:
        con.execute("DELETE FROM revisions")
    restarted = Workflow(flow.home)
    history = restarted.history(proposal["id"])
    assert history["revisions"][0]["action"] == "history_migrated"
    assert "Earlier revisions" in history["revisions"][0]["detail"]


def test_r28_history_bounds_and_immutable_snapshots(review):
    flow, proposal, _, _ = review
    with pytest.raises(ValueError, match="limit"):
        flow.history(proposal["id"], limit=True)
    with pytest.raises(ValueError, match="Historical"):
        flow.get_revision(proposal["id"], 99)
    tampered = copy.deepcopy(proposal)
    tampered["digest"] = "f" * 64
    with flow.connect() as con, pytest.raises(ValueError, match="cannot be rewritten"):
        flow._save(con, tampered, "test")


def downloaded_source(tmp_path):
    folder = tmp_path / "download" / "files"
    folder.mkdir(parents=True)
    source = folder / "orders.csv"
    source.write_text("quantity,price\n1,5\n", encoding="utf-8")
    provenance = {
        "source": "kaggle",
        "license": "MIT",
        "owner": "Test owner",
        "publication_allowed": True,
        "files": [{"path": "orders.csv", "sha256": Workflow._file_hash(source)}],
    }
    (folder.parent / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return source, provenance


@pytest.mark.parametrize("supplied", [{}, {"license": "MIT", "owner": "Test"}])
def test_r29_explicit_provenance_cannot_bypass_download_hash(tmp_path, supplied):
    source, _ = downloaded_source(tmp_path)
    source.write_text("quantity,price\n99,999\n", encoding="utf-8")
    flow = Workflow(tmp_path / ".kc")
    with pytest.raises(ValueError, match="changed since provenance"):
        flow.propose(str(source), provenance=supplied)
    assert flow.list() == []


def test_r29_explicit_license_cannot_override_adjacent_gate(tmp_path):
    source, provenance = downloaded_source(tmp_path)
    provenance.update(license="Unknown", publication_allowed=False)
    (source.parent.parent / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    flow = Workflow(tmp_path / ".kc")
    with pytest.raises(ValueError, match="conflicts"):
        flow.propose(str(source), provenance={"license": "MIT", "publication_allowed": True})


def test_r29_explicit_standalone_hash_is_checked(review):
    flow, _, _, source = review
    with pytest.raises(ValueError, match="hash does not match"):
        flow.propose(str(source), provenance={"sha256": "a" * 64})


def test_r29_source_change_during_analysis_creates_no_proposal(review, monkeypatch):
    from knowledge_catalog import analysis

    flow, _, _, source = review
    original = analysis.analyze_file

    def changing(*args, **kwargs):
        result = original(*args, **kwargs)
        source.write_text("quantity,price\n999,999\n", encoding="utf-8")
        return result

    monkeypatch.setattr(analysis, "analyze_file", changing)
    previous = len(flow.list())
    with pytest.raises(ValueError, match="changed during analysis"):
        flow.propose(str(source))
    assert len(flow.list()) == previous


@pytest.mark.parametrize("mutation", ["remove", "rename", "flags", "statistics", "type"])
def test_r30_column_edits_cannot_erase_observed_evidence(review, mutation):
    flow, proposal, _, _ = review
    columns = copy.deepcopy(proposal["metadata"]["columns"])
    if mutation == "remove":
        columns.pop()
    elif mutation == "rename":
        columns[0]["name"] = "invented"
    elif mutation == "flags":
        columns[0]["pii_flags"] = ["invented"]
    elif mutation == "statistics":
        columns[0]["statistics"]["null_count"] = 999
    else:
        columns[0]["data_type"] = "string"
    with pytest.raises(ValueError, match="Observed"):
        flow.revise(proposal["id"], {"columns": columns})
    assert flow.get(proposal["id"])["revision"] == 1


def test_r30_real_semantic_edit_resets_acknowledgments_even_when_echoed_true(review):
    flow, proposal, _, _ = review
    reviewed = flow.revise(proposal["id"], {"privacy_reviewed": True, "data_quality_reviewed": True})
    assert reviewed["metadata"]["privacy_reviewed"] is True
    changed = flow.revise(
        proposal["id"],
        {"title": "Actual semantic change", "privacy_reviewed": True, "data_quality_reviewed": True},
    )
    assert changed["metadata"]["privacy_reviewed"] is False
    assert changed["metadata"]["data_quality_reviewed"] is False


def test_r30_unchanged_ui_fields_preserve_explicit_human_acknowledgments(review):
    flow, proposal, _, _ = review
    values = {key: copy.deepcopy(proposal["metadata"][key]) for key in ("title", "description", "columns")}
    values.update(privacy_reviewed=True, data_quality_reviewed=True)
    updated = flow.revise(proposal["id"], values)
    assert updated["metadata"]["privacy_reviewed"] is True
    assert updated["metadata"]["data_quality_reviewed"] is True


def test_r30_legacy_proposal_captures_available_source_baseline_on_revision(review):
    from knowledge_catalog.workflow import digest

    flow, proposal, _, _ = review
    proposal.pop("observed_evidence")
    proposal["digest"] = digest({key: proposal[key] for key in ("metadata", "plan", "quality", "revision")})
    store(flow, proposal)
    changed = flow.revise(proposal["id"], {"description": "Reviewed local retail quantities and prices."})
    assert (
        changed["observed_evidence"]["columns"][0]["statistics"]
        == proposal["metadata"]["columns"][0]["statistics"]
    )


def test_r31_mcp_status_is_concise_and_paginated_without_losing_proposals(review, monkeypatch):
    from knowledge_catalog import server

    flow, first, _, source = review
    second = flow.propose(str(source), provenance={"license": "MIT", "owner": "Owner two"})
    monkeypatch.setattr(server, "workflow", lambda: flow)
    page = server.catalog_status(limit=1)
    assert page["total"] == 2 and page["next_offset"] == 1
    assert "report" not in page["proposals"][0]["quality"]
    assert "metadata" not in page["proposals"][0]
    next_page = server.catalog_status(offset=page["next_offset"], limit=1)
    assert {page["proposals"][0]["id"], next_page["proposals"][0]["id"]} == {first["id"], second["id"]}
    assert next_page["next_offset"] is None


def test_r31_mcp_focused_columns_history_and_diff_are_read_only(review, monkeypatch):
    from knowledge_catalog import server

    flow, proposal, _, _ = review
    second = flow.revise(proposal["id"], {"title": "Reviewed retail title"})
    monkeypatch.setattr(server, "workflow", lambda: flow)
    events = flow.events()
    first_page = server.review_proposal(proposal["id"], section="columns", limit=1)
    second_page = server.review_proposal(proposal["id"], section="columns", offset=1, limit=1)
    assert first_page["next_offset"] == 1 and second_page["next_offset"] is None
    assert first_page["columns"][0]["name"] != second_page["columns"][0]["name"]
    assert server.review_proposal(proposal["id"])["metadata"] == second["metadata"]
    assert len(server.proposal_history(proposal["id"])["revisions"]) == 2
    assert server.proposal_diff(proposal["id"], 1)["changes"]
    assert flow.events() == events


@pytest.mark.parametrize("section,offset,limit", [("unknown", 0, 20), ("columns", -1, 20), ("columns", 0, 0)])
def test_r31_mcp_rejects_invalid_section_and_page(review, monkeypatch, section, offset, limit):
    from knowledge_catalog import server

    flow, proposal, _, _ = review
    monkeypatch.setattr(server, "workflow", lambda: flow)
    with pytest.raises(ValueError):
        server.review_proposal(proposal["id"], section=section, offset=offset, limit=limit)


def test_r32_interrupted_process_can_be_recovered_without_cloud_retry(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)

    def interrupted(plan):
        raise SystemExit("simulate abrupt worker termination")

    monkeypatch.setattr(client, "apply_plan", interrupted)
    with pytest.raises(SystemExit):
        flow.publish(proposal["id"])
    crashed = flow.get(proposal["id"])
    assert crashed["status"] == "publishing"
    recovered = flow.recover_publication(
        proposal["id"], crashed["digest"], "Inspected remote state after the worker stopped"
    )
    assert recovered["status"] == "failed" and recovered["approval"] is None
    assert recovered["revision"] == crashed["revision"] + 1
    assert recovered["plan"]["snapshot"]["mode"] == "unverified"
    assert "unknown" in recovered["publication"]["outcome"]
    assert client.applied == 0
    assert flow.events()[0]["action"] == "publication_recovered"
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])


def test_r32_recovery_cannot_interrupt_an_active_publisher(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    entered, release = threading.Event(), threading.Event()

    def paused(plan):
        entered.set()
        assert release.wait(5)
        return {"status": "published", "target": plan["target"]}

    monkeypatch.setattr(client, "apply_plan", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(flow.publish, proposal["id"])
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError, match="in progress"):
                flow.recover_publication(
                    proposal["id"], proposal["digest"], "Would race with live publication"
                )
        finally:
            release.set()
        assert task.result(timeout=5)["status"] == "published"


def test_r32_recovery_is_not_an_mcp_capability(review):
    from knowledge_catalog import server

    tools = server.mcp._tool_manager.list_tools()
    assert not any("recover" in tool.name for tool in tools)


def test_r33_target_change_and_revert_cannot_resurrect_old_approval(review):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    flow.configure(location="europe-west1")
    flow.configure(location="us-central1")
    with pytest.raises(ValueError, match="Configuration changed since human approval"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_r33_configuration_change_is_blocked_while_publisher_runs(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    entered, release = threading.Event(), threading.Event()

    def paused(plan):
        entered.set()
        assert release.wait(5)
        return {"status": "published", "target": plan["target"]}

    monkeypatch.setattr(client, "apply_plan", paused)
    before = flow.config()
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(flow.publish, proposal["id"])
        assert entered.wait(5)
        try:
            with pytest.raises(ValueError, match="in progress"):
                flow.configure(location="europe-west1")
            assert flow.config() == before
        finally:
            release.set()
        assert task.result(timeout=5)["status"] == "published"


def test_r33_publication_uses_one_captured_client_and_checks_external_config_race(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)

    def racing_client():
        config = flow.config()
        config["location"] = "europe-west1"
        flow.config_path.write_text(json.dumps(config), encoding="utf-8")
        return client

    monkeypatch.setattr(flow, "client", racing_client)
    with pytest.raises(ValueError, match="Configuration changed while"):
        flow.publish(proposal["id"])
    assert client.applied == 0
    assert flow.get(proposal["id"])["status"] == "approved"


def test_r33_identical_configuration_does_not_invalidate_human_approval(review):
    flow, proposal, _, _ = review
    proposal = live_approved(flow, proposal)
    flow.configure(project="test-project")
    assert flow.publish(proposal["id"])["status"] == "published"


def test_r43_current_real_policy_blocks_metadata_approved_by_older_validator(review, monkeypatch):
    from knowledge_catalog import ontology

    flow, baseline, client, source = review
    old_quality = copy.deepcopy(baseline["quality"])
    with monkeypatch.context() as old:
        old.setattr(ontology, "validate_metadata", lambda metadata: copy.deepcopy(old_quality))
        proposal = flow.propose(
            str(source),
            provenance={
                "license": "MIT",
                "owner": "Test stewardship",
                "url": "https://example.org/dataset?token=synthetic-test-marker",
            },
        )
        proposal = live_approved(flow, proposal)
    current = ontology.validate_metadata(proposal["metadata"])
    assert any(item["code"] == "SENSITIVE_OR_INVALID_SOURCE_URL" for item in current["findings"])
    with pytest.raises(ValueError, match="blocking quality findings under current validation"):
        flow.publish(proposal["id"])
    assert client.applied == 0
    assert not any(event["action"] == "publishing" for event in flow.events())


@pytest.mark.parametrize("changed", ["warning", "coverage", "rubric"])
def test_r43_material_validation_drift_requires_replan_and_new_approval(review, monkeypatch, changed):
    from knowledge_catalog import ontology

    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    quality = copy.deepcopy(proposal["quality"])
    if changed == "warning":
        quality["score"] -= 3
        quality["findings"].append(
            {"code": "NEW_WARNING", "severity": "warning", "message": "New policy warning"}
        )
    elif changed == "coverage":
        quality["coverage"] = {"mapped_columns": 0, "total_columns": 2, "mapping_fraction": 0.0}
    else:
        quality["rubric"] = "New policy calibration requires a fresh human review."
    monkeypatch.setattr(ontology, "validate_metadata", lambda metadata: copy.deepcopy(quality))
    with pytest.raises(ValueError, match="Validation policy/result changed"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_r43_approve_cannot_bind_new_policy_to_old_stored_score(review, monkeypatch):
    from knowledge_catalog import ontology

    flow, proposal, _, _ = review
    quality = copy.deepcopy(proposal["quality"])
    quality["score"] -= 3
    quality["findings"].append(
        {"code": "NEW_WARNING", "severity": "warning", "message": "Review changed score"}
    )
    monkeypatch.setattr(ontology, "validate_metadata", lambda metadata: quality)
    with pytest.raises(ValueError, match="Validation policy/result changed"):
        flow.approve(proposal["id"], proposal["digest"], "Human tester")
    assert flow.get(proposal["id"])["approval"] is None


def test_r43_report_formatting_and_finding_order_do_not_invalidate_semantic_review(review, monkeypatch):
    from knowledge_catalog import ontology

    flow, baseline, _, source = review
    quality = copy.deepcopy(baseline["quality"])
    quality["findings"].extend(
        [
            {"code": "INFO_A", "severity": "info", "message": "Stable first observation"},
            {"code": "INFO_B", "severity": "info", "message": "Stable second observation"},
        ]
    )
    monkeypatch.setattr(ontology, "validate_metadata", lambda metadata: copy.deepcopy(quality))
    proposal = flow.propose(str(source), provenance={"license": "MIT", "owner": "Test stewardship"})
    proposal = live_approved(flow, proposal)
    quality["report"] = "Different formatting and transient SHACL blank-node identifiers"
    quality["findings"].reverse()
    assert flow.publish(proposal["id"])["status"] == "published"


@pytest.mark.parametrize("missing", ["validation_digest", "validation_policy"])
def test_r43_legacy_approval_without_validation_binding_fails_safe(review, missing):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    proposal["approval"].pop(missing)
    store(flow, proposal)
    with pytest.raises(ValueError, match="current validation policy binding"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_r43_changed_policy_version_needs_new_human_approval(review, monkeypatch):
    flow, proposal, client, _ = review
    proposal = live_approved(flow, proposal)
    monkeypatch.setattr("knowledge_catalog.workflow.VALIDATION_POLICY_VERSION", 2)
    with pytest.raises(ValueError, match="current validation policy binding"):
        flow.publish(proposal["id"])
    assert client.applied == 0
