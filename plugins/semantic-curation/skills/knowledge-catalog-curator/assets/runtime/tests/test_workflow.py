import copy
import json

import pytest

from knowledge_catalog.workflow import Workflow, digest


class FakeClient:
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
def setup(tmp_path, monkeypatch):
    flow = Workflow(tmp_path / ".kc")
    flow.configure(project="test-project", allowed_projects=["test-project"])
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n2,10\n3,12\n")
    client = FakeClient()
    monkeypatch.setattr(flow, "client", lambda: client)
    proposal = flow.propose(str(source), provenance={"license": "MIT", "owner": "Demo team"})
    assert proposal["quality"]["conforms"], proposal["quality"]
    return flow, proposal, client


def test_full_human_approval_lifecycle(setup):
    flow, proposal, client = setup
    flow.configure(writes_enabled=True)
    proposal = flow.replan(proposal["id"], live=True)
    assert proposal["plan"]["metadata"]["quality"]["conforms"]
    flow.approve(proposal["id"], proposal["digest"], "Human tester")
    assert flow.publish(proposal["id"])["status"] == "published"
    assert client.applied == 1
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])


def test_no_write_default_and_no_approval(setup):
    flow, proposal, client = setup
    with pytest.raises(ValueError, match="disabled"):
        flow.publish(proposal["id"])
    flow.configure(writes_enabled=True)
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_offline_approval_cannot_publish(setup):
    flow, proposal, client = setup
    flow.configure(writes_enabled=True)
    flow.approve(proposal["id"], proposal["digest"], "Human tester")
    with pytest.raises(ValueError, match="Offline"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_revise_resets_approval_and_rejects_stale_digest(setup):
    flow, proposal, _ = setup
    flow.approve(proposal["id"], proposal["digest"], "Human tester")
    edited = flow.revise(proposal["id"], {"description": "Reviewed retail order quantities and prices"})
    assert edited["approval"] is None and edited["status"] == "draft"
    with pytest.raises(ValueError, match="changed"):
        flow.approve(proposal["id"], proposal["digest"], "Human tester")


def test_approved_metadata_tampering_is_detected(setup):
    flow, proposal, client = setup
    flow.configure(writes_enabled=True)
    proposal = flow.replan(proposal["id"], live=True)
    approved = flow.approve(proposal["id"], proposal["digest"], "Human tester")
    approved["metadata"]["owner"] = "Changed after approval"
    with flow.connect() as con:
        con.execute("UPDATE proposals SET body=? WHERE id=?", (json.dumps(approved), approved["id"]))
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_expired_and_target_changed_approvals(setup):
    flow, proposal, client = setup
    flow.configure(writes_enabled=True, approval_ttl_seconds=1)
    proposal = flow.replan(proposal["id"], live=True)
    approved = flow.approve(proposal["id"], proposal["digest"], "Human tester")
    approval_at = approved["approval"]["at"]
    approved["approval"]["at"] = 1
    with flow.connect() as con:
        con.execute("UPDATE proposals SET body=? WHERE id=?", (json.dumps(approved), approved["id"]))
    with pytest.raises(ValueError, match="expired"):
        flow.publish(proposal["id"])
    approved["approval"]["at"] = approval_at
    with flow.connect() as con:
        con.execute("UPDATE proposals SET body=? WHERE id=?", (json.dumps(approved), approved["id"]))
    flow.configure(approval_ttl_seconds=86400, location="europe-west1")
    with pytest.raises(ValueError, match="Target changed"):
        flow.publish(proposal["id"])
    assert client.applied == 0


def test_allowlist_and_path_limits(tmp_path):
    flow = Workflow(tmp_path / "workspace" / ".kc")
    with pytest.raises(ValueError, match="allowed_projects"):
        flow.configure(project="test-project", writes_enabled=True)
    source = tmp_path / "outside.txt"
    source.write_text("private document")
    with pytest.raises(ValueError, match="outside"):
        flow.propose(str(source))


def test_failure_requires_new_approval(setup, monkeypatch):
    flow, proposal, client = setup
    flow.configure(writes_enabled=True)
    proposal = flow.replan(proposal["id"], live=True)
    flow.approve(proposal["id"], proposal["digest"], "Human tester")

    def fail(plan):
        raise RuntimeError("remote precondition failed")

    monkeypatch.setattr(client, "apply_plan", fail)
    with pytest.raises(RuntimeError):
        flow.publish(proposal["id"])
    assert flow.get(proposal["id"])["approval"] is None
    assert flow.get(proposal["id"])["status"] == "failed"
    assert flow.events()[0]["action"] == "publication_failed"


def test_digest_is_order_independent():
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_in_progress_blocks_revisions_and_rejections(setup):
    flow, proposal, _ = setup
    proposal["status"] = "publishing"
    with flow.connect() as con:
        flow._save(con, proposal, "test")
    with pytest.raises(ValueError, match="in progress"):
        flow.revise(proposal["id"], {"title": "Changed"})
    with pytest.raises(ValueError, match="in progress"):
        flow.reject(proposal["id"], "Changed")


def test_reject_requires_reason(setup):
    flow, proposal, _ = setup
    with pytest.raises(ValueError):
        flow.reject(proposal["id"], " ")
    assert flow.reject(proposal["id"], "Review source license")["status"] == "rejected"


def test_no_source_rewrite_from_model(setup):
    flow, proposal, _ = setup
    with pytest.raises(ValueError, match="source evidence"):
        flow.revise(proposal["id"], {"source": {"license": "invented"}})
