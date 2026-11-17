import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_stdio_handshake_and_tools(tmp_path):
    async def run():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "knowledge_catalog.server"],
            env={**os.environ, "KC_HOME": str(tmp_path / ".kc")},
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "Knowledge Catalog Curator"
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert {
                    "catalog_inventory",
                    "analyze_document",
                    "review_proposal",
                    "publish_approved",
                } <= names
                assert not any("approve" in name and name != "publish_approved" for name in names)
                result = await session.call_tool("catalog_status", {})
                assert not result.isError
                value = json.loads(result.content[0].text)
                assert value["config"]["writes_enabled"] is False
                denied = await session.call_tool("publish_approved", {"proposal_id": "missing"})
                assert denied.isError

    asyncio.run(run())
