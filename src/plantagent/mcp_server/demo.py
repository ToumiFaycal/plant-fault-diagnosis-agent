"""See the server work: start it as a separate program and talk to it exactly as the agent will.

The demo is the client. It starts the server (`python -m plantagent.mcp_server --episode ...`),
connects over stdio, lists the tools, calls each one, and shows one deliberate mistake coming back
as an error the model could read.

Run it with:
    python -m plantagent.mcp_server.demo
    python -m plantagent.mcp_server.demo --episode ep_3f9a1c2e   (any episode from episodes/dev.jsonl)
"""

import argparse
import asyncio
import json
import sys

from mcp import Client, StdioServerParameters

from plantagent.episodes.build import sample_time

DEFAULT_EPISODE = "ep_f6f8d79c"


def show(title: str, result) -> None:
    print(f"\n=== {title}")
    if result.is_error:
        print("is_error = True:", result.content[0].text)
    else:
        print(json.dumps(result.structured_content, indent=2, ensure_ascii=False))


async def talk_to_server(episode: str) -> None:
    server = StdioServerParameters(command=sys.executable, args=["-m", "plantagent.mcp_server", "--episode", episode])
    async with Client(server) as client:  # starts the server program; stops it at the end of the block
        listing = await client.list_tools()
        print("Tools offered by the server:")
        for tool in listing.tools:
            print(f"  {tool.name}: {tool.description.splitlines()[0]}")

        info = await client.call_tool("get_episode_info", {})
        show("get_episode_info()", info)

        reactor = await client.call_tool("list_tags", {"process_unit": "reactor"})
        show('list_tags(process_unit="reactor")', reactor)

        now = info.structured_content["now_sample"]
        hour_ago = sample_time(max(now - 20, 1))
        trend = await client.call_tool("get_trend", {"tag": "xmeas_9", "window_start": hour_ago,
                                                     "window_end": "48:00", "max_points": 5})
        show(f'get_trend("xmeas_9", "{hour_ago}", "48:00", max_points=5): the end is after now', trend)

        future = await client.call_tool("get_trend", {"tag": "xmeas_9", "window_start": "47:00", "window_end": "48:00"})
        show('get_trend("xmeas_9", "47:00", "48:00"): a window entirely after now', future)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the plant-historian server for one episode and call its tools.")
    parser.add_argument("--episode", default=DEFAULT_EPISODE)
    asyncio.run(talk_to_server(parser.parse_args().episode))


if __name__ == "__main__":
    main()
