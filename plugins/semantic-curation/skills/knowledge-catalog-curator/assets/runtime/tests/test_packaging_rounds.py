import asyncio
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from knowledge_catalog import __version__

ROOT = Path(__file__).parents[1]


def test_r42_versions_and_launchers_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    code = json.loads((ROOT / "plugin/.claude-plugin/plugin.json").read_text())
    desktop = json.loads((ROOT / "desktop/manifest.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert (
        project["project"]["version"]
        == code["version"]
        == desktop["version"]
        == marketplace["plugins"][0]["version"]
        == __version__
    )
    assert (ROOT / "plugin/run-server.cjs").read_bytes() == (ROOT / "desktop/run-server.cjs").read_bytes()
    assert "Machine-local" in desktop["long_description"]


def test_r42_missing_runtime_reports_actionable_error_without_protocol_noise(tmp_path):
    result = subprocess.run(
        [shutil.which("node"), str(ROOT / "plugin/run-server.cjs")],
        env={**os.environ, "KC_RUNTIME_CONFIG": str(tmp_path / "missing.json")},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 1
    assert result.stdout == "" and "register-claude" in result.stderr


def test_r42_real_node_launcher_negotiates_current_mcp_tools(tmp_path):
    runtime = tmp_path / "runtime.json"
    runtime.write_text(
        json.dumps({"python": sys.executable, "home": str(tmp_path / ".kc")}), encoding="utf-8"
    )

    async def run():
        async with asyncio.timeout(30):
            params = StdioServerParameters(
                command=shutil.which("node"),
                args=[str(ROOT / "plugin/run-server.cjs")],
                env={**os.environ, "KC_RUNTIME_CONFIG": str(runtime)},
            )
            async with stdio_client(params) as (reader, writer):
                async with ClientSession(reader, writer) as session:
                    await session.initialize()
                    tools = {tool.name for tool in (await session.list_tools()).tools}
                    assert {
                        "proposal_history",
                        "proposal_diff",
                        "review_proposal",
                        "open_review_panel",
                    } <= tools
                    assert "recover_publication" not in tools and "approve" not in tools
                    result = await session.call_tool("catalog_status", {})
                    assert not result.isError
                    status = json.loads(result.content[0].text)
                    assert status["config"]["writes_enabled"] is False

    asyncio.run(run())
