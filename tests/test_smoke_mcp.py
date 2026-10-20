"""Smoke test for MCP: the library is installed, uses its version 2 names, and a client
can list and call the tools of a server.

The real plant server comes later. This one is a toy with a single tool, so that if
something breaks here, we know the problem is MCP itself and not our plant code.
"""

import asyncio

from mcp import Client
from mcp.server import MCPServer

toy_server = MCPServer("smoke-test")


@toy_server.tool()
def add(a: int, b: int) -> int:
    """Add two whole numbers."""
    return a + b


async def talk_to_toy_server(arguments: dict):
    """Connect a client to the toy server, list its tools, and call `add` with these arguments."""
    async with Client(toy_server) as client:  # in memory: the server object is handed over directly
        listing = await client.list_tools()
        result = await client.call_tool("add", arguments)
    return listing, result


def test_client_can_list_and_call_a_tool():
    listing, result = asyncio.run(talk_to_toy_server({"a": 2, "b": 3}))

    assert [tool.name for tool in listing.tools] == ["add"]
    assert result.is_error is False
    assert result.structured_content == {"result": 5}


def test_a_bad_call_comes_back_as_an_error_not_a_crash():
    _, result = asyncio.run(talk_to_toy_server({"a": 2}))  # "b" is missing

    assert result.is_error is True
