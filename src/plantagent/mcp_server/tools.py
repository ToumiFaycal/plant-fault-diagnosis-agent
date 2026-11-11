"""What each tool does, as plain Python functions (server.py plugs them into MCP).

Kept apart from the MCP plumbing so each one can be read and tested on its own:
episode (and arguments) in, a filled-in result form (models.py) out.
"""

import numpy as np
import pandas as pd
from mcp.server.mcpserver.exceptions import ToolError

from plantagent.config import PROJECT_ROOT
from plantagent.episodes.build import MINUTES_PER_SAMPLE, sample_time
from plantagent.mcp_server.episode import Episode
from plantagent.docsearch import DocIndex, search
from plantagent.mcp_server.models import (Contributor, Contributors, DocSearchResult, DocSection, EpisodeInfo,
                                          MonitorStatus, NormalComparison, ScoreVsLimit, SignalVsNormal, TagInfo,
                                          TagList, Trend, TrendPoint)
from plantagent.mcp_server.windows import clip_window, clock_to_sample, evenly_spaced
from plantagent.monitor.alarms import alarm_run
from plantagent.monitor.contributions import contributions_of_run, top_contributors
from plantagent.monitor.data import SIGNALS
from plantagent.monitor.scores import score_run

TAGS = pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")
PROCESS_UNITS = list(dict.fromkeys(TAGS["process_unit"]))  # each unit once, in the order of tags.csv
Z_THRESHOLD = 2.0  # a window average at least 2 normal wobbles away counts as "up" or "down"


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

# --- The monitor's tools (step 7.2) ---

def safe_window(episode: Episode, window_start: str, window_end: str) -> tuple[pd.DataFrame, dict]:
    """The rows of a requested window, cut at now (with your clip_window), and the window fields
    every windowed result carries (see WindowResult in models.py)."""
    asked_start, asked_end = clock_to_sample(window_start), clock_to_sample(window_end)
    start, end = clip_window(asked_start, asked_end, episode.now_sample)
    rows = episode.table[(episode.table["sample"] >= start) & (episode.table["sample"] <= end)]
    fields = {"window_start": sample_time(start), "window_end": sample_time(end), "window_start_sample": start,
              "window_end_sample": end, "clipped_to_now": asked_end > episode.now_sample, "samples_in_window": len(rows)}
    return rows, fields


def z_score_and_direction(window_mean: float, normal_mean: float, normal_std: float) -> tuple[float, str]:
    """How unusual a window's average is, as (z_score, direction).

    z_score: how many normal wobbles the window's average is away from the normal average (+ above,
             - below). Example: normal 120.40 °C, wobble 0.02 °C, window average 120.46 °C -> z = +3.
    direction: "up" if z_score >= Z_THRESHOLD (2), "down" if z_score <= -Z_THRESHOLD, otherwise "normal".
    """
    z = (window_mean - normal_mean) / normal_std if normal_std > 0 else 0
    if z >= Z_THRESHOLD:
        direction = "up"
    elif z <= -Z_THRESHOLD:
        direction = "down"
    else:
        direction = "normal"
    return z, direction


def comparison(episode: Episode, monitor: dict, tags: list[str], window_start: str, window_end: str,
               call_id: str) -> NormalComparison:
    rows, fields = safe_window(episode, window_start, window_end)
    signals = []
    for tag in tags:
        info = check_tag(tag)
        column = SIGNALS.index(tag)
        normal_mean, normal_std = float(monitor["averages"][column]), float(monitor["wobbles"][column])
        window_mean = float(rows[tag].mean())
        z, direction = z_score_and_direction(window_mean, normal_mean, normal_std)
        signals.append(SignalVsNormal(tag=tag, description=info["description"], engineering_unit=info["engineering_unit"],
                                      window_mean=compact(window_mean), normal_mean=compact(normal_mean),
                                      normal_std=compact(normal_std), z_score=compact(z), direction=direction))
    return NormalComparison(call_id=call_id, **fields, signals=signals)


def score_vs_limit(scores: np.ndarray, limit: float, rows: pd.DataFrame) -> ScoreVsLimit:
    highest = int(np.argmax(scores))
    return ScoreVsLimit(limit=compact(limit), highest=compact(scores[highest]),
                        highest_sample_time=rows["sample_time"].iloc[highest],
                        moments_above_limit=int(np.sum(scores > limit)))


def monitor_status(episode: Episode, monitor: dict, window_start: str, window_end: str, call_id: str) -> MonitorStatus:
    rows, fields = safe_window(episode, window_start, window_end)
    t2, spe = score_run(monitor, rows[SIGNALS].to_numpy())

    # The alarm rule counts moments in a row, so look from the start of the run: a streak that began
    # before the window still counts inside it.
    in_a_row = monitor["alarm_after_consecutive"]
    until_end = episode.table[episode.table["sample"] <= fields["window_end_sample"]]
    alarm = alarm_run(monitor, until_end[SIGNALS].to_numpy(), in_a_row)
    alarm_in_window = alarm[(until_end["sample"] >= fields["window_start_sample"]).to_numpy()]
    first = int(np.argmax(alarm_in_window)) if alarm_in_window.any() else None

    return MonitorStatus(
        call_id=call_id, **fields,
        t2=score_vs_limit(t2, monitor["t2_limit"], rows),
        spe=score_vs_limit(spe, monitor["spe_limit"], rows),
        alarm_rule=f"alarm when T² or SPE stays above its limit for {in_a_row} moments in a row",
        moments_in_alarm=int(alarm_in_window.sum()),
        first_alarm_time=None if first is None else rows["sample_time"].iloc[first],
        first_alarm_sample=None if first is None else int(rows["sample"].iloc[first]),
    )


def contributors(episode: Episode, monitor: dict, window_start: str, window_end: str, k: int, statistic: str,
                 call_id: str) -> Contributors:
    rows, fields = safe_window(episode, window_start, window_end)
    X = rows[SIGNALS].to_numpy()
    t2, spe = score_run(monitor, X)
    scores, limit = (t2, monitor["t2_limit"]) if statistic == "T2" else (spe, monitor["spe_limit"])
    ranked = top_contributors(contributions_of_run(monitor, X, statistic), k)  # your step 6 functions
    return Contributors(
        call_id=call_id, **fields, statistic=statistic, average_score=compact(scores.mean()), limit=compact(limit),
        contributors=[Contributor(rank=rank, tag=tag, description=check_tag(tag)["description"],
                                  process_unit=check_tag(tag)["process_unit"], share_percent=round(share * 100, 1))
                      for rank, (tag, share) in enumerate(ranked, start=1)],
    )


# --- Searching the documents (step 7.3) ---

def document_search(docs: DocIndex, query: str, results: int, cutoff: float, call_id: str) -> DocSearchResult:
    try:
        found = search(docs, query, results, cutoff)  # your cosine_similarities does the comparing
    except ConnectionError:  # the question's meaning is computed by Ollama, which must be running
        raise ToolError("The document search is unavailable right now (Ollama is not running).") from None
    return DocSearchResult(
        call_id=call_id, query=query, cutoff=cutoff,
        sections=[DocSection(section_id=section.section_id, title=section.title,
                             similarity=round(similarity, 3), text=section.text)
                  for section, similarity in found],
    )
