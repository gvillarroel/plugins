import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_catalog.lineage_interface import attach_record, export_record, render_lineage, store
from knowledge_catalog.ui import make_server
from knowledge_catalog.workflow import Workflow


def approved_simulation(flow):
    lineage = store(flow.home)
    record = lineage.create_demo()
    record = lineage.revise(
        record["id"], {"edges": record["graph"]["observed_dependencies"]}, record["digest"]
    )
    return lineage.approve(record["id"], record["digest"], "QA ONLY")


@pytest.mark.parametrize("invalid", [None, "", False, "abc", "A" * 64])
def test_attachment_requires_metadata_digest_even_over_http(tmp_path, invalid):
    flow = Workflow(tmp_path / ".kc")
    with pytest.raises(ValueError, match="proposal_digest"):
        attach_record(flow, "missing", "missing", "a" * 64, invalid)


def test_attaching_approved_graph_rechecks_evidence_and_metadata_revision(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    flow.configure(project="test-project")
    source = tmp_path / "orders.csv"
    source.write_text("quantity,price\n2,10\n3,12\n")
    proposal = flow.propose(str(source), provenance={"license": "MIT", "owner": "QA demo"})
    record = approved_simulation(flow)
    changed = flow.revise(proposal["id"], {"title": "New reviewed title"})
    with pytest.raises(ValueError, match="changed"):
        attach_record(flow, record["id"], proposal["id"], record["digest"], proposal["digest"])
    attached = attach_record(flow, record["id"], changed["id"], record["digest"], changed["digest"])
    relation = attached["metadata"]["relationships"][-1]
    assert relation["graph"] == record["graph"] and relation["synthetic"] is True
    assert attached["status"] == "draft" and attached["approval"] is None
    dataset = record["graph"]["datasets"][0]
    path = flow.home / "lineage-data" / record["id"] / dataset["path"]
    path.write_text("changed after approval")
    with pytest.raises(ValueError, match="CSV evidence changed"):
        attach_record(flow, record["id"], attached["id"], record["digest"], attached["digest"])
    assert flow.get(attached["id"])["digest"] == attached["digest"]


def test_browser_scripts_parse_and_offline_mutations_are_disabled(tmp_path):
    if not shutil.which("node"):
        pytest.skip("Node.js is required for bundled browser script syntax validation")
    record = store(tmp_path / ".kc").create_demo()
    html = render_lineage(record, embedded=True)
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    assert len(scripts) == 2
    for number, script in enumerate(scripts):
        path = tmp_path / f"script-{number}.js"
        path.write_text(script, encoding="utf-8")
        subprocess.run(["node", "--check", str(path)], capture_output=True, check=True)
    assert "data-write" in html and '"export-ol"' in html


@pytest.fixture
def lineage_ui(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    server, url = make_server(flow, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base, token = url.split("#")

    def action(name, **arguments):
        request = Request(
            base + "api/action",
            json.dumps({"action": "lineage_" + name, **arguments}).encode(),
            headers={
                "Authorization": "Bearer " + token,
                "Origin": base.rstrip("/"),
                "Content-Type": "application/json",
            },
        )
        with urlopen(request) as response:
            return json.load(response)

    yield flow, base, token, action
    server.shutdown()
    server.server_close()
    thread.join()


def test_http_graph_and_exact_revision_decisions(lineage_ui):
    flow, base, token, action = lineage_ui
    with urlopen(base + "lineage") as response:
        html = response.read().decode()
        assert token not in html and 'id="graph-title"' in html and 'lang="en"' in html
        assert "sha256-" in response.headers["Content-Security-Policy"]
    with pytest.raises(HTTPError) as denied:
        urlopen(base + "api/lineage")
    assert denied.value.code == 401
    record = action("demo", seed=17)
    assert not record["quality"]["conforms"]
    fixed = action(
        "revise",
        id=record["id"],
        updates={"edges": record["graph"]["observed_dependencies"]},
        expected_digest=record["digest"],
    )
    with pytest.raises(HTTPError) as stale:
        action("approve", id=record["id"], expected_digest=record["digest"], reviewer="QA ONLY")
    assert stale.value.code == 409
    approved = action("approve", id=fixed["id"], expected_digest=fixed["digest"], reviewer="QA ONLY")
    assert approved["status"] == "approved"
    newer = action(
        "revise",
        id=fixed["id"],
        expected_digest=fixed["digest"],
        updates={"notes": "A newly documented limitation for QA."},
    )
    assert newer["approval"] is None and newer["status"] == "draft"
    assert store(flow.home).get(record["id"])["digest"] == newer["digest"]


def test_http_lineage_history_diff_export_restore_and_rejection(lineage_ui):
    _, _, _, action = lineage_ui
    original = action("demo", seed=123)
    fixed = action(
        "revise",
        id=original["id"],
        expected_digest=original["digest"],
        updates={"edges": original["graph"]["observed_dependencies"]},
    )
    history = action("history", id=fixed["id"])
    assert len(history["items"]) == 2
    assert action("revision", id=fixed["id"], revision=1)["graph"] == original["graph"]
    difference = action("diff", id=fixed["id"], from_revision=1)
    assert difference["changes"] and difference["to_revision"] == 2
    bundle = action(
        "export",
        id=fixed["id"],
        expected_digest=fixed["digest"],
        format="openlineage",
        project="test-project",
    )
    assert len(bundle["events"]) == 4 and bundle["review"]["status"] == "draft"
    restored = action("restore", id=fixed["id"], revision=1, expected_digest=fixed["digest"])
    assert restored["revision"] == 3 and not restored["quality"]["conforms"]
    rejected = action(
        "reject",
        id=restored["id"],
        expected_digest=restored["digest"],
        reason="QA ONLY: review the unsupported relationship",
    )
    assert rejected["status"] == "rejected" and rejected["approval"] is None
    assert "QA ONLY" in json.dumps(action("history", id=restored["id"]))


def test_snapshot_escapes_script_and_has_no_runtime_connection(tmp_path):
    record = store(tmp_path).create_demo()
    record["graph"]["title"] = '</script><script>alert("injection")</script>'
    html = render_lineage(record)
    assert record["graph"]["title"] not in html
    assert "\\u003c/script>" in html
    assert 'id="initial-record"' in html
    assert "<!--HOST_BRIDGE-->" in html
    assert 'id="offline"' in html
    assert export_record(record)["digest"] == record["digest"]
    with pytest.raises(ValueError, match="format"):
        export_record(record, "unsupported")


def test_unapproved_graph_cannot_be_attached(tmp_path):
    flow = Workflow(tmp_path / ".kc")
    record = store(flow.home).create_demo()
    with pytest.raises(ValueError, match="approval"):
        attach_record(flow, record["id"], "missing", record["digest"], "a" * 64)
    with pytest.raises(ValueError, match="expected_digest"):
        attach_record(flow, record["id"], "missing", "wrong", "a" * 64)


def test_cli_unicode_redirect_and_snapshot_export(tmp_path):
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    command = [sys.executable, "-m", "knowledge_catalog.cli", "--home", str(tmp_path / ".kc")]
    demo = subprocess.run([*command, "lineage-demo"], capture_output=True, env=env, check=True)
    record = json.loads(demo.stdout.decode("utf-8"))
    destination = tmp_path / "preview.html"
    exported = subprocess.run(
        [*command, "lineage-export", record["id"], "--format", "html", "--output", str(destination)],
        capture_output=True,
        check=True,
    )
    assert json.loads(exported.stdout)["export_only"]
    assert 'id="initial-record"' in destination.read_text(encoding="utf-8")
    again = subprocess.run(
        [*command, "lineage-export", record["id"], "--format", "html", "--output", str(destination)],
        capture_output=True,
    )
    assert again.returncode == 1 and b"FileExistsError" in again.stderr


def test_real_mcp_apps_resource_and_edits(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "knowledge_catalog.server"],
            env={**os.environ, "KC_HOME": str(tmp_path / ".kc")},
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = {tool.name: tool for tool in (await session.list_tools()).tools}
                assert tools["review_lineage"].meta["ui"]["resourceUri"] == "ui://kc/lineage.html"
                assert not any("approve" in name and name != "publish_approved" for name in tools)
                resource = await session.read_resource("ui://kc/lineage.html")
                content = resource.contents[0]
                assert content.mimeType == "text/html;profile=mcp-app"
                assert content.meta["ui"]["csp"]["connectDomains"] == []
                assert "kcHost" in content.text
                demo = await session.call_tool("create_lineage_demo", {"seed": 33})
                assert not demo.isError
                record = demo.structuredContent
                revised = await session.call_tool(
                    "revise_lineage",
                    {
                        "id": record["id"],
                        "expected_digest": record["digest"],
                        "updates": {"edges": record["graph"]["observed_dependencies"]},
                    },
                )
                assert not revised.isError and revised.structuredContent["quality"]["conforms"]
                assert revised.structuredContent["approval"] is None
                history = await session.call_tool("lineage_history", {"id": record["id"]})
                assert len(history.structuredContent["items"]) == 2

    asyncio.run(run())
