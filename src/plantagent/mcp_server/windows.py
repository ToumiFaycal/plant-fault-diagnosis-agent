"""Time inside an episode: clock times like "08:30" (counted from the start of the run) and sample numbers.

The most important rule of the whole server lives here: a tool never shows anything after "now".
"""

import re

import numpy as np
from mcp.server.mcpserver.exceptions import ToolError

from plantagent.episodes.build import MINUTES_PER_SAMPLE, sample_time

CLOCK_PATTERN = r"^\d{1,2}:\d{2}$"  # "08:30" or "8:30": hours and minutes from the start of the run


def clock_to_sample(clock: str) -> int:
    """The sample taken at a clock time: "08:30" -> 170 (8.5 hours x 20 samples per hour).

    A time between two samples gives the sample just before it ("08:31" -> 170).
    """
    if re.fullmatch(CLOCK_PATTERN, clock.strip()) is None:
        raise ToolError(f"{clock!r} is not a time in HH:MM form (hours and minutes from the start of the run, like '08:30').")
    hours, minutes = (int(part) for part in clock.strip().split(":"))
    if minutes >= 60:
        raise ToolError(f"{clock!r} has {minutes} minutes; minutes go from 00 to 59.")
    return (hours * 60 + minutes) // MINUTES_PER_SAMPLE


def clip_window(start: int, end: int, now: int) -> tuple[int, int]:
    """Make a requested window of samples safe, and return it as (start, end).

    - The data starts at sample 1: a start before that becomes 1.
    - Nothing after now: an end after `now` becomes `now`.
    - If the window goes backwards (start after end), or starts after now, there is nothing to show:
      raise a ToolError with a message the model can read and act on.
    """
    if start > end:
        raise ToolError(f"window_start {start} is after window_end {end}.")
    if start > now:
        raise ToolError(f"window_start {start} is after now ({sample_time(now)}). Nothing after now exists.")
    return max(start, 1), min(end, now)


def evenly_spaced(count: int, max_points: int) -> np.ndarray:
    """Positions of at most `max_points` items out of `count`, spread evenly, always keeping the first
    and the last one: evenly_spaced(100, 5) -> [0, 25, 50, 74, 99]."""
    if count <= max_points:
        return np.arange(count)
    return np.unique(np.linspace(0, count - 1, max_points).round().astype(int))
