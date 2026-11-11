"""Tests for the plant-historian MCP server: the tools answer correctly, never show anything after
"now", report mistakes as readable errors, and the server code never touches the answers."""

import asyncio
import json

import numpy as np
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.episodes.build import episode_table
from plantagent.mcp_server.episode import Episode, load_episode
from plantagent.mcp_server.server import build_server
from plantagent.mcp_server.windows import clip_window, clock_to_sample, evenly_spaced
from plantagent.monitor.data import SIGNALS


def made_up_episode() -> Episode:
    """An episode whose "now" is sample 100 (05:00), where every signal equals its sample number.
    Its table wrongly holds 20 moments too many, to check that the tools still stop at now."""
    X = np.repeat(np.arange(1, 121, dtype=float).reshape(-1, 1), len(SIGNALS), axis=1)
    return Episode(name="ep_00000000", trigger_message="The plant monitor raised an alarm at 04:00. It is now 05:00.",
                   now_sample=100, table=episode_table(X, 120))


async def call_tools(calls: list[tuple[str, dict]]) -> list:
    """Connect one client to a server for the made-up episode and make these tool calls, in order."""
    async with Client(build_server(made_up_episode())) as client:
        return [await client.call_tool(name, arguments) for name, arguments in calls]


def call_tool(name: str, arguments: dict | None = None):
    return asyncio.run(call_tools([(name, arguments or {})]))[0]


# --- Time windows (clip_window is yours) ---

def test_clock_times_become_sample_numbers():
    assert clock_to_sample("08:30") == 170  # 8.5 hours x 20 samples per hour
    assert clock_to_sample("00:03") == 1
    assert clock_to_sample("08:31") == 170  # between two samples: the one before


def test_a_badly_written_time_is_a_clear_error():
    with pytest.raises(ToolError):
        clock_to_sample("8h30")
    with pytest.raises(ToolError):
        clock_to_sample("08:75")


def test_a_window_inside_the_data_is_unchanged():
    assert clip_window(10, 50, now=100) == (10, 50)


def test_a_window_ending_after_now_is_cut_at_now():
    assert clip_window(80, 300, now=100) == (80, 100)


def test_a_window_starting_before_the_data_starts_at_sample_1():
    assert clip_window(0, 50, now=100) == (1, 50)


def test_a_window_entirely_after_now_is_an_error():
    with pytest.raises(ToolError):
        clip_window(150, 200, now=100)


def test_a_backwards_window_is_an_error():
    with pytest.raises(ToolError):
        clip_window(50, 10, now=100)


def test_evenly_spaced_keeps_the_first_and_the_last():
    assert list(evenly_spaced(100, 5)) == [0, 25, 50, 74, 99]
    assert list(evenly_spaced(3, 5)) == [0, 1, 2]  # fewer items than asked for: keep them all


# --- The server and its tools ---

def test_the_server_offers_three_read_only_tools():
    async def list_tools():
        async with Client(build_server(made_up_episode())) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools()).tools
    assert {tool.name for tool in tools} == {"get_episode_info", "list_tags", "get_trend"}
    assert all(tool.annotations.read_only_hint for tool in tools)


def test_episode_info_gives_the_trigger_and_now():
    info = call_tool("get_episode_info").structured_content
    assert info["trigger_message"].startswith("The plant monitor raised an alarm at 04:00")
    assert info["now_time"] == "05:00" and info["now_sample"] == 100
    assert "reactor" in info["process_units"]


def test_list_tags_for_one_process_unit():
    tags = call_tool("list_tags", {"process_unit": "reactor"}).structured_content["tags"]
    assert {tag["process_unit"] for tag in tags} == {"reactor"}
    assert "xmeas_9" in [tag["tag"] for tag in tags]  # reactor temperature


def test_an_unknown_process_unit_is_a_readable_error():
    result = call_tool("list_tags", {"process_unit": "boiler"})
    assert result.is_error
    assert "reactor" in result.content[0].text  # the message lists the units that do exist


def test_a_trend_never_goes_past_now():
    trend = call_tool("get_trend", {"tag": "xmeas_9", "window_start": "04:00", "window_end": "10:00"}).structured_content
    assert trend["clipped_to_now"] is True
    assert trend["window_end"] == "05:00" and trend["window_end_sample"] == 100
    assert max(point["sample"] for point in trend["points"]) == 100
    assert trend["last"] == 100.0  # the stored table goes on to 120, but now is 100


def test_a_trend_summary_uses_the_whole_window():
    trend = call_tool("get_trend", {"tag": "xmeas_9", "window_start": "04:00", "window_end": "05:00",
                                    "max_points": 5}).structured_content
    assert trend["clipped_to_now"] is False
    assert trend["samples_in_window"] == 21  # samples 80 to 100
    assert (trend["minimum"], trend["maximum"], trend["mean"]) == (80.0, 100.0, 90.0)
    assert (trend["first"], trend["last"]) == (80.0, 100.0)
    assert [point["sample"] for point in trend["points"]] == [80, 85, 90, 95, 100]  # only 5 of the 21
    assert trend["points"][0]["sample_time"] == "04:00"


def test_a_trend_of_an_unknown_tag_is_a_readable_error():
    result = call_tool("get_trend", {"tag": "xmeas_99", "window_start": "04:00", "window_end": "05:00"})
    assert result.is_error
    assert "list_tags" in result.content[0].text  # tells the model how to find the right name


def test_a_trend_window_after_now_is_an_error_not_data():
    result = call_tool("get_trend", {"tag": "xmeas_9", "window_start": "06:00", "window_end": "07:00"})
    assert result.is_error


def test_each_call_gets_its_own_call_id():
    first, second = asyncio.run(call_tools([("get_episode_info", {}), ("list_tags", {})]))
    assert first.structured_content["call_id"] == "c1"
    assert second.structured_content["call_id"] == "c2"


# --- No answers, ever ---

def test_the_server_code_never_mentions_the_answers():
    # The answer key and the processed data (which has the fault number in it) must stay out of reach.
    forbidden = ("labels_", "faultnumber", "simulationrun", "processed")
    for path in (PROJECT_ROOT / "src" / "plantagent" / "mcp_server").glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert not any(word in text for word in forbidden), f"{path.name} mentions an answer source"


def test_only_episode_lists_can_be_opened():
    with pytest.raises(ValueError):
        load_episode("ep_00000000", split="labels_dev")


EPISODE_LIST = PROJECT_ROOT / "episodes" / "dev.jsonl"
EPISODES_DIR = PROJECT_ROOT / load_config()["data"]["episodes_dir"]


@pytest.mark.skipif(not EPISODES_DIR.exists(), reason="no episode files on this computer (they're never on GitHub)")
def test_a_real_episode_stops_at_its_now():
    first = json.loads(EPISODE_LIST.read_text(encoding="utf-8").splitlines()[0])
    episode = load_episode(first["episode"])
    assert episode.table["sample"].max() == first["now_sample"]
    assert list(episode.table.columns) == ["sample", "sample_time"] + SIGNALS
