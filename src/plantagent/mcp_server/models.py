"""What each tool sends back, as fixed forms with named fields (Pydantic models).

Fixed forms mean the agent's code and the evidence checker can always find each number by its
name. Every result carries a call_id: the agent must cite it for every claim in its report, and
the checker looks the claim up in the result with that ID.

Times always have explicit names (window_start, window_end, sample_time, now_time) and the HH:MM
form, counted from the start of the run, next to the sample number.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    call_id: str = Field(description="ID of this tool call. Cite it as evidence for anything you take from this result.")


class EpisodeInfo(ToolResult):
    trigger_message: str = Field(description="Why this investigation was started.")
    first_sample_time: str = Field(description="Clock time of the first data available (HH:MM from the start of the run).")
    now_time: str = Field(description="Clock time of now, the last data available. Nothing after it exists.")
    now_sample: int = Field(description="Sample number of now.")
    minutes_per_sample: int = Field(description="Minutes between two samples.")
    process_units: list[str] = Field(description="Process units that list_tags can filter on.")


class TagInfo(BaseModel):
    tag: str
    description: str
    engineering_unit: str
    process_unit: str
    new_value_every_min: int = Field(description="How often the signal gets a new value (analysers are slow).")
    delay_min: int = Field(description="How late each new value arrives (analysers report with a delay).")


class TagList(ToolResult):
    process_unit: str | None = Field(description="The process unit asked for, or null for all tags.")
    tags: list[TagInfo]


class TrendPoint(BaseModel):
    sample: int
    sample_time: str = Field(description="Clock time of this sample (HH:MM from the start of the run).")
    value: float


class WindowResult(ToolResult):
    """The fields every tool that looks at a time window returns, so the window is never ambiguous."""
    window_start: str = Field(description="Clock time of the first sample in the window (after clipping).")
    window_end: str = Field(description="Clock time of the last sample in the window (after clipping).")
    window_start_sample: int
    window_end_sample: int
    clipped_to_now: bool = Field(description="True if the requested window ended after now and was cut at now.")
    samples_in_window: int = Field(description="How many samples the window holds (the results use all of them).")


class Trend(WindowResult):
    tag: str
    description: str
    engineering_unit: str
    minimum: float
    maximum: float
    mean: float
    first: float = Field(description="Value at window_start.")
    last: float = Field(description="Value at window_end.")
    points: list[TrendPoint] = Field(description="At most max_points values, spread evenly over the window.")


class SignalVsNormal(BaseModel):
    tag: str
    description: str
    engineering_unit: str
    window_mean: float = Field(description="The signal's average over the window.")
    normal_mean: float = Field(description="Its average in healthy plant runs.")
    normal_std: float = Field(description="Its normal wobble (standard deviation) in healthy plant runs.")
    z_score: float = Field(description="(window_mean - normal_mean) / normal_std: how many normal wobbles away. + above, - below.")
    direction: Literal["up", "down", "normal"] = Field(description="up if z_score >= 2, down if z_score <= -2, otherwise normal.")


class NormalComparison(WindowResult):
    signals: list[SignalVsNormal]


class ScoreVsLimit(BaseModel):
    limit: float = Field(description="The alarm limit: only 1 % of healthy moments score above it.")
    highest: float = Field(description="Highest score in the window.")
    highest_sample_time: str = Field(description="Clock time of the highest score.")
    moments_above_limit: int


class MonitorStatus(WindowResult):
    t2: ScoreVsLimit = Field(description="T², strange amount: the plant moves in its usual ways, but too far.")
    spe: ScoreVsLimit = Field(description="SPE, strange pattern: signals move together in a way a healthy plant doesn't.")
    alarm_rule: str
    moments_in_alarm: int
    first_alarm_time: str | None = Field(description="First moment inside the window when the monitor was in alarm "
                                                     "(window_start if the alarm was already on). null: no alarm in the window.")
    first_alarm_sample: int | None


class Contributor(BaseModel):
    rank: int
    tag: str
    description: str
    process_unit: str
    share_percent: float = Field(description="This signal's share of the score over the window, in %.")


class Contributors(WindowResult):
    statistic: Literal["T2", "SPE"]
    average_score: float = Field(description="The score's average over the window.")
    limit: float = Field(description="The score's alarm limit.")
    contributors: list[Contributor] = Field(description="Biggest share first. All 52 shares add up to 100 %.")
