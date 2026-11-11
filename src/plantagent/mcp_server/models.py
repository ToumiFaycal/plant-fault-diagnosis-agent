"""What each tool sends back, as fixed forms with named fields (Pydantic models).

Fixed forms mean the agent's code and the evidence checker can always find each number by its
name. Every result carries a call_id: the agent must cite it for every claim in its report, and
the checker looks the claim up in the result with that ID.

Times always have explicit names (window_start, window_end, sample_time, now_time) and the HH:MM
form, counted from the start of the run, next to the sample number.
"""

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


class Trend(ToolResult):
    tag: str
    description: str
    engineering_unit: str
    window_start: str = Field(description="Clock time of the first sample in the window (after clipping).")
    window_end: str = Field(description="Clock time of the last sample in the window (after clipping).")
    window_start_sample: int
    window_end_sample: int
    clipped_to_now: bool = Field(description="True if the requested window ended after now and was cut at now.")
    samples_in_window: int = Field(description="How many samples the window holds (the summary uses all of them).")
    minimum: float
    maximum: float
    mean: float
    first: float = Field(description="Value at window_start.")
    last: float = Field(description="Value at window_end.")
    points: list[TrendPoint] = Field(description="At most max_points values, spread evenly over the window.")
