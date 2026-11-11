"""The plant-historian MCP server: the agent's only way to see the plant.

One server serves one episode. The agent starts it for the episode it investigates, asks it
questions through its tools, and stops it at the end. All tools only read, and every time window
is cut at the episode's "now".

What the model sees of each tool comes from this file: the function name, its docstring, and the
description of each argument. Writing them clearly is part of the design.

Run by hand (normally the agent starts it), after saving the monitor once
(python -m plantagent.monitor.saved):
    python -m plantagent.mcp_server --episode ep_f6f8d79c
It then waits for an MCP client on stdio (standard input and output), so it shows nothing itself.
"""

import argparse
import itertools
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field

from plantagent.mcp_server import tools
from plantagent.mcp_server.episode import EPISODE_LISTS, Episode, load_episode
from plantagent.mcp_server.models import Contributors, EpisodeInfo, MonitorStatus, NormalComparison, TagList, Trend
from plantagent.mcp_server.windows import CLOCK_PATTERN
from plantagent.monitor.saved import load_monitor, monitor_path

READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)  # changes nothing; closed set of data

INSTRUCTIONS = (
    "Tools to investigate one alarm in a simulated chemical plant (the Tennessee Eastman Process). "
    "Start with get_episode_info. Times are HH:MM counted from the start of the run; nothing after "
    "'now' is available. Every result has a call_id: cite it for each claim you make."
)

Clock = Annotated[str, Field(pattern=CLOCK_PATTERN, description="A time as HH:MM from the start of the run, like '08:30'.")]


def build_server(episode: Episode, monitor: dict) -> MCPServer:
    """An MCP server whose tools can see this episode, and only this episode, plus the saved monitor."""
    server = MCPServer("plant-historian", instructions=INSTRUCTIONS)
    call_numbers = itertools.count(1)

    def next_call_id() -> str:
        return f"c{next(call_numbers)}"  # c1, c2, c3... in the order of the calls

    @server.tool(annotations=READ_ONLY)
    def get_episode_info() -> EpisodeInfo:
        """Start here. Why this investigation was started, the data available (from the start of the
        run to now), how often the plant is sampled, and the process units list_tags can filter on."""
        return tools.episode_info(episode, next_call_id())

    @server.tool(annotations=READ_ONLY)
    def list_tags(
        process_unit: Annotated[str | None, Field(description="Only the tags of this process unit, like 'reactor'. Leave out for all 52 tags.")] = None,
    ) -> TagList:
        """The plant's signals (tags): what each one is, its engineering unit, its process unit, how
        often it gets a new value and how late that value arrives. Tags named xmeas_* are measurements;
        tags named xmv_* are valves that the plant's controllers move."""
        return tools.tag_list(process_unit, next_call_id())

    @server.tool(annotations=READ_ONLY)
    def get_trend(
        tag: Annotated[str, Field(description="One tag, like 'xmeas_9'.")],
        window_start: Clock,
        window_end: Clock,
        max_points: Annotated[int, Field(ge=2, le=200, description="Most values to return, spread evenly over the window.")] = 40,
    ) -> Trend:
        """How one signal changed over a time window: the minimum, maximum, mean, first and last value
        of the whole window, and up to max_points values spread evenly over it. A window that ends
        after now is cut at now."""
        return tools.trend(episode, tag, window_start, window_end, max_points, next_call_id())

    @server.tool(annotations=READ_ONLY)
    def compare_to_normal(
        tags: Annotated[list[str], Field(min_length=1, max_length=12, description="1 to 12 tags, like ['xmeas_9', 'xmv_10'].")],
        window_start: Clock,
        window_end: Clock,
    ) -> NormalComparison:
        """How far each signal's average over the window is from its average in healthy plant runs,
        counted in normal wobbles (the z-score). direction is "up" when z_score >= 2, "down" when
        z_score <= -2, otherwise "normal". Cite these results for claims that a signal is above or
        below normal."""
        return tools.comparison(episode, monitor, tags, window_start, window_end, next_call_id())

    @server.tool(annotations=READ_ONLY)
    def get_monitor_status(window_start: Clock, window_end: Clock) -> MonitorStatus:
        """What the plant monitor saw in a window. It has two scores, each with an alarm limit:
        T² ("strange amount": the plant moves in its usual ways, but too far) and SPE ("strange
        pattern": signals move together in a way a healthy plant doesn't). Gives each score's highest
        value and how many moments were above its limit, and the first moment in alarm."""
        return tools.monitor_status(episode, monitor, window_start, window_end, next_call_id())

    @server.tool(annotations=READ_ONLY)
    def top_contributors(
        window_start: Clock,
        window_end: Clock,
        k: Annotated[int, Field(ge=1, le=15, description="How many signals to return.")] = 6,
        statistic: Annotated[Literal["T2", "SPE"], Field(description="Which monitor score to split between the signals.")] = "T2",
    ) -> Contributors:
        """Which signals carry the monitor's score over a window, biggest share first (the shares of
        all 52 signals add up to 100 %). They show where the strangeness appears, which is not always
        where a problem started: controllers move valves to hold measurements steady."""
        return tools.contributors(episode, monitor, window_start, window_end, k, statistic, next_call_id())

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="The plant-historian MCP server, for one episode, over stdio.")
    parser.add_argument("--episode", required=True, help="the episode's name, like ep_f6f8d79c")
    parser.add_argument("--split", default="dev", choices=EPISODE_LISTS, help="which episode list it is in")
    arguments = parser.parse_args()
    if not monitor_path().exists():
        raise SystemExit("The saved monitor is missing: run  python -m plantagent.monitor.saved  first.")
    episode, monitor = load_episode(arguments.episode, arguments.split), load_monitor(monitor_path())
    build_server(episode, monitor).run()  # stdio: stdin/stdout carry the messages


if __name__ == "__main__":
    main()
