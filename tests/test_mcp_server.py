"""Tests for the plant-historian MCP server: the tools answer correctly, never show anything after
"now", report mistakes as readable errors, and the server code never touches the answers."""

import asyncio
import json
import re
from types import SimpleNamespace

import numpy as np
import pytest
from mcp import Client
from mcp.server.mcpserver.exceptions import ToolError

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.docsearch import DocIndex, Section
from plantagent.episodes.build import episode_table
from plantagent.mcp_server.episode import Episode, load_episode
from plantagent.mcp_server.server import build_server
from plantagent.mcp_server.tools import z_score_and_direction
from plantagent.mcp_server.windows import clip_window, clock_to_sample, evenly_spaced
from plantagent.monitor.data import SIGNALS
from plantagent.monitor.saved import load_monitor, monitor_path


def made_up_episode() -> Episode:
    """An episode whose "now" is sample 100 (05:00), where every signal equals its sample number.
    Its table wrongly holds 20 moments too many, to check that the tools still stop at now."""
    X = np.repeat(np.arange(1, 121, dtype=float).reshape(-1, 1), len(SIGNALS), axis=1)
    return Episode(name="ep_00000000", trigger_message="The plant monitor raised an alarm at 04:00. It is now 05:00.",
                   now_sample=100, table=episode_table(X, 120))


def made_up_monitor() -> dict:
    """A monitor simple enough to work out by hand: every signal's normal average is 50 and its
    wobble 10, so a value v has z = (v - 50) / 10. It keeps 2 ways of moving (signals 1 and 2 alone),
    so with all 52 signals equal: T² = 2 z² and SPE = 50 z². Both limits are passed exactly when
    |z| > 2, that is v > 70 or v < 30."""
    patterns = SimpleNamespace(components_=np.eye(len(SIGNALS))[:2], explained_variance_=np.ones(2))
    return {"averages": np.full(len(SIGNALS), 50.0), "wobbles": np.full(len(SIGNALS), 10.0), "patterns": patterns,
            "kept": 2, "t2_limit": 8.0, "spe_limit": 200.0, "alarm_after_consecutive": 3}


def made_up_docs() -> DocIndex:
    """Three document sections whose "meanings" point in three different directions, and a made-up
    way to turn a question into an arrow (a 4th direction stands for "something else")."""
    sections = [Section(f"doc#{name}", name.title(), f"About the {name}.") for name in ("reactor", "condenser", "stripper")]
    questions = {"mostly the reactor": [0.8, 0.6, 0.0, 0.0],  # similarities 0.8, 0.6 and 0
                 "something else": [0.0, 0.0, 0.0, 1.0]}       # similar to nothing

    def embed_query(query: str) -> np.ndarray:
        if query == "ollama is off":
            raise ConnectionError("Failed to connect to Ollama.")
        return np.array(questions[query])

    return DocIndex(sections=sections, vectors=np.eye(4)[:3], embed_query=embed_query)


def made_up_server():
    return build_server(made_up_episode(), made_up_monitor(), made_up_docs())


async def call_tools(calls: list[tuple[str, dict]]) -> list:
    """Connect one client to a server for the made-up episode and make these tool calls, in order."""
    async with Client(made_up_server()) as client:
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

def test_the_server_offers_seven_read_only_tools():
    async def list_tools():
        async with Client(made_up_server()) as client:
            return await client.list_tools()

    tools = asyncio.run(list_tools()).tools
    assert {tool.name for tool in tools} == {"get_episode_info", "list_tags", "get_trend", "compare_to_normal",
                                             "get_monitor_status", "top_contributors", "search_docs"}
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


# --- The monitor's tools (z_score_and_direction is yours) ---
# Reminder: in the made-up episode every signal equals its sample number, and in the made-up monitor
# z = (value - 50) / 10. So samples 80-100 (04:00-05:00) average 90 -> z = +4.

def test_z_score_and_direction():
    assert z_score_and_direction(90.0, 50.0, 10.0) == (4.0, "up")
    assert z_score_and_direction(30.0, 50.0, 10.0) == (-2.0, "down")  # exactly 2 wobbles below counts
    assert z_score_and_direction(51.0, 50.0, 10.0) == (0.1, "normal")
    assert z_score_and_direction(120.46, 120.40, 0.02)[1] == "up"  # the reactor example: z = 3


def test_compare_to_normal_up_down_and_normal():
    def first_signal(window_start, window_end):
        result = call_tool("compare_to_normal", {"tags": ["xmeas_9"], "window_start": window_start,
                                                 "window_end": window_end}).structured_content
        return result["signals"][0]

    up = first_signal("04:00", "05:00")  # samples 80-100, average 90
    assert (up["window_mean"], up["normal_mean"], up["normal_std"]) == (90.0, 50.0, 10.0)
    assert (up["z_score"], up["direction"]) == (4.0, "up")
    assert first_signal("01:00", "02:00")["direction"] == "down"  # samples 20-40, average 30: z = -2
    assert first_signal("02:00", "03:00")["direction"] == "normal"  # samples 40-60, average 50: z = 0


def test_compare_to_normal_also_stops_at_now():
    result = call_tool("compare_to_normal", {"tags": ["xmeas_9", "xmv_10"], "window_start": "04:00",
                                             "window_end": "10:00"}).structured_content
    assert result["clipped_to_now"] is True and result["window_end"] == "05:00"
    assert [signal["tag"] for signal in result["signals"]] == ["xmeas_9", "xmv_10"]
    assert result["signals"][0]["window_mean"] == 90.0  # 80-100 only: with the future rows it would be 100


def test_monitor_status_waits_for_three_moments_in_a_row():
    # Above both limits from sample 71 (value 71 > 70). Three in a row: in alarm from sample 73 (03:39).
    status = call_tool("get_monitor_status", {"window_start": "03:00", "window_end": "04:00"}).structured_content
    assert status["t2"]["moments_above_limit"] == 10  # samples 71-80
    assert (status["first_alarm_time"], status["first_alarm_sample"]) == ("03:39", 73)
    assert status["moments_in_alarm"] == 8  # samples 73-80


def test_monitor_status_counts_a_streak_that_began_before_the_window():
    # The window starts at sample 74 (03:42); the streak began at 71, so the alarm is already on.
    status = call_tool("get_monitor_status", {"window_start": "03:42", "window_end": "04:00"}).structured_content
    assert status["first_alarm_time"] == "03:42"


def test_monitor_status_of_a_quiet_window():
    status = call_tool("get_monitor_status", {"window_start": "02:00", "window_end": "03:00"}).structured_content
    assert status["first_alarm_time"] is None and status["moments_in_alarm"] == 0
    assert status["spe"]["moments_above_limit"] == 0


def test_monitor_status_highest_score():
    status = call_tool("get_monitor_status", {"window_start": "04:00", "window_end": "05:00"}).structured_content
    assert (status["t2"]["limit"], status["spe"]["limit"]) == (8.0, 200.0)
    assert status["t2"]["highest"] == 50.0  # sample 100: z = 5, T² = 2 x 5²
    assert status["t2"]["highest_sample_time"] == "05:00"


def test_top_contributors_split_the_score():
    # T² only looks along the 2 kept ways (signals 1 and 2): they share it half and half.
    t2 = call_tool("top_contributors", {"window_start": "04:00", "window_end": "05:00", "k": 2}).structured_content
    assert {c["tag"] for c in t2["contributors"]} == {"xmeas_1", "xmeas_2"}
    assert [c["share_percent"] for c in t2["contributors"]] == [50.0, 50.0]
    assert [c["rank"] for c in t2["contributors"]] == [1, 2]
    # SPE is the leftover: the other 50 signals, 2 % each.
    spe = call_tool("top_contributors", {"window_start": "04:00", "window_end": "05:00", "k": 3,
                                         "statistic": "SPE"}).structured_content
    assert len(spe["contributors"]) == 3
    assert all(c["share_percent"] == 2.0 and c["tag"] not in ("xmeas_1", "xmeas_2") for c in spe["contributors"])


def test_a_monitor_tool_window_after_now_is_an_error():
    result = call_tool("top_contributors", {"window_start": "06:00", "window_end": "07:00"})
    assert result.is_error


# --- Searching the documents ---

def test_search_docs_gives_the_most_similar_sections_with_their_ids():
    result = call_tool("search_docs", {"query": "mostly the reactor"}).structured_content
    assert result["cutoff"] == load_config()["docs"]["cutoff"]
    assert [(s["section_id"], s["similarity"]) for s in result["sections"]] == [("doc#reactor", 0.8),
                                                                              ("doc#condenser", 0.6)]
    assert result["sections"][0]["text"] == "About the reactor."


def test_search_docs_can_find_nothing():
    assert call_tool("search_docs", {"query": "something else"}).structured_content["sections"] == []


def test_search_docs_without_ollama_is_a_readable_error():
    result = call_tool("search_docs", {"query": "ollama is off"})
    assert result.is_error
    assert "Ollama" in result.content[0].text


# --- The saved monitor ---

def test_the_saved_monitor_scores_like_the_original(tmp_path):
    from plantagent.monitor.saved import save_monitor
    from plantagent.monitor.scores import score_run

    random = np.random.default_rng(0)
    ways = np.linalg.qr(random.normal(size=(len(SIGNALS), 5)))[0].T  # 5 made-up ways, at right angles
    original = {"averages": random.normal(size=len(SIGNALS)), "wobbles": random.uniform(0.5, 2, size=len(SIGNALS)),
                "patterns": SimpleNamespace(components_=ways, explained_variance_=np.array([5.0, 4, 3, 2, 1])),
                "kept": 3, "t2_limit": 12.3, "spe_limit": 45.6, "alarm_after_consecutive": 3}
    save_monitor(original, tmp_path / "monitor.npz")
    loaded = load_monitor(tmp_path / "monitor.npz")

    X = random.normal(size=(30, len(SIGNALS)))
    for before, after in zip(score_run(original, X), score_run(loaded, X)):
        assert np.allclose(before, after)
    assert (loaded["kept"], loaded["t2_limit"], loaded["spe_limit"]) == (3, 12.3, 45.6)


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


@pytest.mark.skipif(not (EPISODES_DIR.exists() and monitor_path().exists()),
                    reason="needs the episode files and the saved monitor (never on GitHub)")
def test_the_server_finds_the_same_first_alarm_as_the_episode_builder():
    from plantagent.mcp_server.tools import monitor_status

    monitor = load_monitor(monitor_path())
    entries = [json.loads(line) for line in EPISODE_LIST.read_text(encoding="utf-8").splitlines()]
    alarm_entries = [entry for entry in entries if "raised an alarm at" in entry["trigger_message"]]
    assert alarm_entries
    for entry in alarm_entries:
        alarm_time = re.search(r"alarm at (\d+:\d{2})", entry["trigger_message"]).group(1)
        status = monitor_status(load_episode(entry["episode"]), monitor, "00:00", entry["now_time"], "c1")
        assert status.first_alarm_time == alarm_time, entry["episode"]
