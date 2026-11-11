"""What each tool does, as plain Python functions (server.py plugs them into MCP).

Kept apart from the MCP plumbing so each one can be read and tested on its own:
episode (and arguments) in, a filled-in result form (models.py) out.
"""

import pandas as pd
from mcp.server.mcpserver.exceptions import ToolError

from plantagent.config import PROJECT_ROOT
from plantagent.episodes.build import MINUTES_PER_SAMPLE, sample_time
from plantagent.mcp_server.episode import Episode
from plantagent.mcp_server.models import EpisodeInfo, TagInfo, TagList, Trend, TrendPoint
from plantagent.mcp_server.windows import clip_window, clock_to_sample, evenly_spaced

TAGS = pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")
PROCESS_UNITS = list(dict.fromkeys(TAGS["process_unit"]))  # each unit once, in the order of tags.csv


def compact(value: float) -> float:
    """A value with 6 significant digits (2705.07, 120.405, 0.337120): enough for the plant, and short
    for a small model to read."""
    return float(f"{value:.6g}")


def check_tag(tag: str) -> pd.Series:
    """The row of tags.csv for this tag, or an error the model can act on."""
    rows = TAGS[TAGS["tag"] == tag]
    if rows.empty:
        raise ToolError(f"Unknown tag {tag!r}. Tags look like 'xmeas_9' or 'xmv_10'; call list_tags to see all 52.")
    return rows.iloc[0]


def episode_info(episode: Episode, call_id: str) -> EpisodeInfo:
    return EpisodeInfo(
        call_id=call_id,
        trigger_message=episode.trigger_message,
        first_sample_time=sample_time(1),
        now_time=sample_time(episode.now_sample),
        now_sample=episode.now_sample,
        minutes_per_sample=MINUTES_PER_SAMPLE,
        process_units=PROCESS_UNITS,
    )


def tag_list(process_unit: str | None, call_id: str) -> TagList:
    if process_unit is None:
        rows = TAGS
    else:
        rows = TAGS[TAGS["process_unit"] == process_unit]
        if rows.empty:
            raise ToolError(f"Unknown process unit {process_unit!r}. Choose one of: {', '.join(PROCESS_UNITS)}.")
    return TagList(call_id=call_id, process_unit=process_unit,
                   tags=[TagInfo(**row) for row in rows.to_dict(orient="records")])


def trend(episode: Episode, tag: str, window_start: str, window_end: str, max_points: int, call_id: str) -> Trend:
    """How one signal changed over a window, cut at now: a summary of every value, plus at most
    `max_points` of them spread evenly."""
    info = check_tag(tag)  # stops here with a clear error if the tag doesn't exist
    asked_start, asked_end = clock_to_sample(window_start), clock_to_sample(window_end)  # also checks the format
    start, end = clip_window(asked_start, asked_end, episode.now_sample)  # keep the SAFE window it gives back
    rows = episode.table[(episode.table["sample"] >= start) & (episode.table["sample"] <= end)]
    values = rows[tag].to_numpy()
    points = [TrendPoint(sample=int(rows.iloc[position]["sample"]),
                         sample_time=rows.iloc[position]["sample_time"],
                         value=compact(rows.iloc[position][tag]))
              for position in evenly_spaced(len(rows), max_points)]
    return Trend(
        call_id=call_id,
        tag=tag,
        description=info["description"],
        engineering_unit=info["engineering_unit"],
        window_start=sample_time(start),  # the window actually used, after clipping
        window_end=sample_time(end),
        window_start_sample=start,
        window_end_sample=end,
        clipped_to_now=asked_end > episode.now_sample,
        samples_in_window=len(rows),
        minimum=compact(values.min()),
        maximum=compact(values.max()),
        mean=compact(values.mean()),
        first=compact(values[0]),
        last=compact(values[-1]),
        points=points,
    )