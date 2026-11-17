"""Independent phase-three checks across real MCP transport and curation state."""

import asyncio
import hashlib
import json
import os
import sys
from datetime import timedelta

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_catalog.workflow import Workflow


def saved_download(tmp_path):
    root = tmp_path / "kaggle" / "publisher" / "retail" / "v1"
    folder = root / "files"
    folder.mkdir(parents=True)
    source = folder / "orders.csv"
    source.write_text("order_id,quantity,price\n1,2,10\n2,3,20\n", encoding="utf-8")
    provenance = {
        "source": "kaggle",
        "handle": "publisher/retail",
        "dataset_version": 1,
        "source_url": "https://www.kaggle.com/datasets/publisher/retail",
        "license": {"name": "MIT", "spdx_id": "MIT", "evidence": "Kaggle API licenseName"},
        "publication_allowed": True,
        "synthetic": {
            "publisher_claim": True,
            "independently_verified": False,
            "evidence": ["Publisher states these orders were generated synthetically."],
        },
        "files": [{"path": "orders.csv", "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}],
        "local_directory": str(root),
        "local_files": [str(source)],
    }
    (root / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return source, provenance


def test_real_mcp_curates_verified_download_but_cannot_assert_human_review_or_approve(tmp_path):
    source, _ = saved_download(tmp_path)
    flow = Workflow(tmp_path / ".kc")
    flow.configure(project="test-project", allowed_projects=["test-project"], writes_enabled=True)

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "knowledge_catalog.server"],
            env={**os.environ, "KC_HOME": str(flow.home)},
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=30)) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert not any("approve" in name and name != "publish_approved" for name in tools)
                assert "path" in tools["analyze_document"].inputSchema["required"]
                assert tools["analyze_document"].inputSchema["properties"]["path"]["type"] == "string"
                assert tools["revise_metadata"].inputSchema["properties"]["updates"]["type"] == "object"
                proposal_result = await session.call_tool("analyze_document", {"path": str(source)})
                assert not proposal_result.isError
                proposal = json.loads(proposal_result.content[0].text)
                assert proposal["metadata"]["source"]["license"] == "MIT"
                assert proposal["metadata"]["source"]["synthetic"] is True
                assert "local_directory" not in proposal["metadata"]["source"]
                assert proposal["approval"] is None
                for assertion in ("privacy_reviewed", "data_quality_reviewed"):
                    denied = await session.call_tool(
                        "revise_metadata", {"proposal_id": proposal["id"], "updates": {assertion: True}}
                    )
                    assert denied.isError
                    assert "Human review" in denied.content[0].text
                revised_result = await session.call_tool(
                    "revise_metadata",
                    {"proposal_id": proposal["id"], "updates": {"owner": "Retail test stewardship"}},
                )
                assert not revised_result.isError
                revised = json.loads(revised_result.content[0].text)
                assert revised["quality"]["conforms"] is True
                assert revised["revision"] == proposal["revision"] + 1
                assert revised["metadata"]["quality"] == revised["quality"]
                assert revised["plan"]["metadata"]["quality"] == revised["quality"]
                denied = await session.call_tool("publish_approved", {"proposal_id": proposal["id"]})
                assert denied.isError and "human approval" in denied.content[0].text
                assert flow.get(proposal["id"])["status"] == "draft"
                assert not any(event["action"] == "publishing" for event in flow.events())

    asyncio.run(run())


def test_changed_download_cannot_reuse_verified_provenance(tmp_path):
    source, _ = saved_download(tmp_path)
    source.write_text("order_id,quantity,price\n1,999,999\n", encoding="utf-8")
    flow = Workflow(tmp_path / ".kc")
    with pytest.raises(ValueError, match="changed since provenance"):
        flow.propose(str(source))
    assert flow.list() == []


def test_human_offline_approval_still_cannot_publish(tmp_path):
    source, _ = saved_download(tmp_path)
    flow = Workflow(tmp_path / ".kc")
    flow.configure(project="test-project", allowed_projects=["test-project"], writes_enabled=True)
    proposal = flow.propose(str(source))
    proposal = flow.revise(proposal["id"], {"owner": "Retail test stewardship"})
    assert proposal["quality"]["conforms"] is True
    flow.approve(proposal["id"], proposal["digest"], "Human integration tester")
    with pytest.raises(ValueError, match="Offline preview"):
        flow.publish(proposal["id"])
    revised = flow.revise(proposal["id"], {"concepts": proposal["metadata"]["concepts"]})
    assert revised["approval"] is None
    assert revised["digest"] != proposal["digest"]
    with pytest.raises(ValueError, match="human approval"):
        flow.publish(proposal["id"])


def test_source_identity_and_approval_fields_cannot_be_revised(tmp_path):
    source, _ = saved_download(tmp_path)
    flow = Workflow(tmp_path / ".kc")
    proposal = flow.propose(str(source))
    for changes in (
        {"source": {"sha256": "f" * 64}},
        {"approval": {"reviewer": "model"}},
        {"quality_findings": []},
        {"status": "approved"},
    ):
        with pytest.raises(ValueError, match="source evidence and hashes cannot be edited"):
            flow.revise(proposal["id"], changes)
    assert flow.get(proposal["id"])["revision"] == proposal["revision"]


def test_unknown_upstream_license_blocks_approval_after_metadata_override(tmp_path):
    source, provenance = saved_download(tmp_path)
    provenance["publication_allowed"] = False
    provenance["license"] = {"name": "Unknown", "spdx_id": None, "review_status": "unknown"}
    (source.parent.parent / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    flow = Workflow(tmp_path / ".kc")
    proposal = flow.propose(str(source))
    proposal = flow.revise(proposal["id"], {"owner": "Retail test stewardship", "license": "MIT"})
    assert proposal["quality"]["conforms"] is False
    assert any(finding["code"] == "UNKNOWN_LICENSE" for finding in proposal["quality"]["findings"])
    with pytest.raises(ValueError, match="blocking quality"):
        flow.approve(proposal["id"], proposal["digest"], "Human integration tester")


def test_nested_download_files_keep_verified_provenance(tmp_path):
    source, provenance = saved_download(tmp_path)
    nested = source.parent / "tables" / "retail" / source.name
    nested.parent.mkdir(parents=True)
    source.rename(nested)
    provenance["files"][0]["path"] = "tables/retail/orders.csv"
    (source.parent.parent / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    proposal = Workflow(tmp_path / ".kc").propose(str(nested))
    assert proposal["metadata"]["source"]["handle"] == "publisher/retail"
    assert proposal["metadata"]["source"]["license"] == "MIT"
