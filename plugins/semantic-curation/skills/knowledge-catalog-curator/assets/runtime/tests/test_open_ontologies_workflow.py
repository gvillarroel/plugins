"""Real-engine integration and catalog boundaries, separate from mocked adapter tests."""

import asyncio
import copy
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_catalog.open_ontologies import OpenOntologiesError, runtime_status
from knowledge_catalog.workflow import Workflow


@pytest.fixture
def proposal(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n2,10\n3,12\n", encoding="utf-8")
    value = flow.propose(str(source), provenance={"license": "MIT", "owner": "Engine integration fixture"})
    return flow, value


@pytest.fixture
def real_engine():
    status = runtime_status()
    if not status["available"]:
        pytest.skip("Install the pinned official engine to run native integration tests")
    return status


def test_real_engine_lookup_is_read_only_and_saved_choice_invalidates_approval(proposal, real_engine):
    flow, draft = proposal
    approved = flow.approve(draft["id"], draft["digest"], "Synthetic integration reviewer")
    events = flow.events()
    result = flow.taxonomy_suggestions(
        approved["id"], column_name="quantity", expected_digest=approved["digest"], provider="open-ontologies"
    )
    assert result["provider"]["invoked"] is True
    assert result["provider"]["version"] == "2.1.0"
    assert result["provider"]["binary_sha256"] == real_engine["binary_sha256"]
    assert result["provider"]["mode"] == "dry-run"
    assert flow.get(approved["id"]) == approved and flow.events() == events
    candidate = result["candidates"][0]
    assert candidate["label"] == "Quantity"
    assert candidate["score"] == candidate["engine_evidence"]["confidence"]
    assert candidate["engine_evidence"]["requires_review"] is False
    assert candidate["requires_human_review"] is True
    assert "label_similarity" in candidate["engine_evidence"]["informative_signals"]
    columns = copy.deepcopy(approved["metadata"]["columns"])
    columns[0]["concepts"] = [
        {
            "concept": candidate["concept"],
            "label": candidate["label"],
            "confidence": candidate["score"],
            "provider": result["provider"],
            "engine_evidence": candidate["engine_evidence"],
            "requires_human_review": True,
            "evidence": "Explicit synthetic test selection from the actual Open Ontologies dry run.",
        }
    ]
    updated = flow.revise(approved["id"], {"columns": columns}, expected_digest=result["digest"])
    assert updated["approval"] is None and updated["status"] == "draft"
    assert updated["observed_evidence"] == approved["observed_evidence"]
    with pytest.raises(ValueError, match="changed; reload"):
        flow.taxonomy_suggestions(updated["id"], expected_digest=result["digest"], provider="open-ontologies")


def test_engine_failure_never_silently_returns_local_candidates(proposal, monkeypatch):
    flow, draft = proposal

    def unavailable(*args, **kwargs):
        raise OpenOntologiesError("Verified engine unavailable")

    monkeypatch.setattr("knowledge_catalog.open_ontologies.compare_concepts", unavailable)
    with pytest.raises(OpenOntologiesError, match="unavailable"):
        flow.taxonomy_suggestions(draft["id"], column_name="quantity", provider="open-ontologies")
    local = flow.taxonomy_suggestions(draft["id"], column_name="quantity", provider="local")
    assert local["provider"]["id"] == "local" and local["provider"]["invoked"] is False
    assert flow.get(draft["id"]) == draft


@pytest.mark.parametrize("provider", ["other", None, True, [], {}])
def test_unknown_provider_cannot_start_an_engine(proposal, provider):
    flow, draft = proposal
    with pytest.raises(ValueError, match="provider must"):
        flow.taxonomy_suggestions(draft["id"], provider=provider)
    assert flow.get(draft["id"]) == draft


def test_actual_curator_mcp_tool_delegates_to_native_engine(proposal, real_engine):
    flow, draft = proposal

    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "knowledge_catalog.server"],
            env={**os.environ, "KC_HOME": str(flow.home)},
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                for name in ("open_ontologies_status", "compare_taxonomy_with_open_ontologies"):
                    assert tools[name].annotations.readOnlyHint is True
                status = await session.call_tool("open_ontologies_status", {})
                assert not status.isError and status.structuredContent["available"] is True
                result = await session.call_tool(
                    "compare_taxonomy_with_open_ontologies",
                    {
                        "proposal_id": draft["id"],
                        "column_name": "quantity",
                        "expected_digest": draft["digest"],
                    },
                )
                assert not result.isError
                value = result.structuredContent
                assert value["provider"]["invoked"] is True
                assert value["provider"]["binary_sha256"] == real_engine["binary_sha256"]
                assert value["candidates"][0]["engine_evidence"]["confidence"] == 1.0

    asyncio.run(run())
    assert flow.get(draft["id"]) == draft
