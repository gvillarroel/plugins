"""Suggestion transport and stewardship tests: lookup is never a decision."""

import asyncio
import copy
import json
import os
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_catalog.ui import make_server
from knowledge_catalog.workflow import Workflow


@pytest.fixture
def proposed(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n2,10\n3,12\n", encoding="utf-8")
    proposal = flow.propose(str(source), provenance={"license": "MIT", "owner": "Taxonomy test team"})
    assert proposal["quality"]["conforms"]
    return flow, proposal


def test_lookup_binds_saved_revision_without_changing_history_or_approval(proposed):
    flow, draft = proposed
    approved = flow.approve(draft["id"], draft["digest"], "Synthetic test reviewer")
    events = flow.events()
    history = flow.history(approved["id"])
    response = flow.taxonomy_suggestions(
        approved["id"], column_name="quantity", expected_digest=approved["digest"]
    )
    assert response["proposal_id"] == approved["id"]
    assert response["digest"] == approved["digest"]
    assert response["revision"] == approved["revision"]
    assert response["column_name"] == "quantity"
    assert response["candidates"][0]["label"] == "Quantity"
    assert response["method"]["score_is_probability"] is False
    assert flow.get(draft["id"]) == approved
    assert flow.events() == events and flow.history(approved["id"]) == history


def test_stale_lookup_and_changed_mapping_preserve_normal_revision_contract(proposed):
    flow, draft = proposed
    approved = flow.approve(draft["id"], draft["digest"], "Synthetic test reviewer")
    result = flow.taxonomy_suggestions(approved["id"], column_name="quantity")
    candidate = result["candidates"][0]
    columns = copy.deepcopy(approved["metadata"]["columns"])
    columns[0].update(
        semantic_type=candidate["label"],
        semantic_confidence=candidate["score"],
        description="Number of units recorded in this source field; units still require review.",
        concepts=[
            {
                "concept": candidate["concept"],
                "label": candidate["label"],
                "confidence": candidate["score"],
                "evidence": "Explicit test selection from vocabulary " + result["vocabulary"]["version"],
            }
        ],
    )
    revised = flow.revise(approved["id"], {"columns": columns}, expected_digest=result["digest"])
    assert revised["revision"] == approved["revision"] + 1
    assert revised["approval"] is None and revised["status"] == "draft"
    assert revised["observed_evidence"] == approved["observed_evidence"]
    with pytest.raises(ValueError, match="changed; reload"):
        flow.taxonomy_suggestions(revised["id"], column_name="quantity", expected_digest=result["digest"])


@pytest.mark.parametrize("column,query", [("absent", ""), ("quantity", "x" * 301), ("quantity", [])])
def test_invalid_lookup_keeps_the_draft_unchanged(proposed, column, query):
    flow, proposal = proposed
    with pytest.raises(ValueError):
        flow.taxonomy_suggestions(proposal["id"], column_name=column, query=query)
    assert flow.get(proposal["id"]) == proposal


def test_http_lookup_auth_origin_and_stale_binding(proposed):
    flow, proposal = proposed
    server, address = make_server(flow, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base, token = address.split("#")

    def request(*, bearer=token, origin=None, expected=proposal["digest"], **extra):
        return Request(
            base + "api/action",
            data=json.dumps(
                {
                    "action": "taxonomy_suggest",
                    "id": proposal["id"],
                    "expected_digest": expected,
                    "column_name": "quantity",
                    **extra,
                }
            ).encode(),
            headers={
                "Authorization": "Bearer " + bearer,
                "Origin": origin or base.rstrip("/"),
                "Content-Type": "application/json",
            },
        )

    try:
        with urlopen(request()) as response:
            assert json.load(response)["candidates"][0]["label"] == "Quantity"
        for req, expected in (
            (request(bearer="invalid"), 401),
            (request(origin="https://attacker.invalid"), 403),
            (request(expected="0" * 64), 409),
            (request(query="x" * 301), 400),
        ):
            with pytest.raises(HTTPError) as error:
                urlopen(req)
            assert error.value.code == expected
        assert flow.get(proposal["id"]) == proposal
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_real_mcp_taxonomy_tool_is_read_only_and_leaves_proposal_unapproved(proposed):
    flow, proposal = proposed

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
                assert tools["suggest_taxonomy"].annotations.readOnlyHint is True
                assert not any("approve" in name and name != "publish_approved" for name in tools)
                response = await session.call_tool(
                    "suggest_taxonomy",
                    {
                        "proposal_id": proposal["id"],
                        "column_name": "quantity",
                        "expected_digest": proposal["digest"],
                    },
                )
                assert not response.isError
                assert response.structuredContent["digest"] == proposal["digest"]
                assert response.structuredContent["candidates"][0]["label"] == "Quantity"

    asyncio.run(run())
    assert flow.get(proposal["id"]) == proposal
