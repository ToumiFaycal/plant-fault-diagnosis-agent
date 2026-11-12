"""The form the agent fills in at the end of an investigation: the Diagnosis.

A form with fixed boxes, not a free letter, so that code can check the evidence and grade the
answer. At the end of an investigation Ollama is asked to answer in exactly this shape (its
`format` option takes the form's JSON schema), and Pydantic checks the answer fits.

The descriptions below are read by the model: they are its instructions for each box.

The evidence comes first in the form on purpose: the model writes its clues before its
conclusion, like a detective listing the facts before naming a culprit.
"""

from typing import Annotated, Literal

import pandas as pd
from pydantic import BaseModel, Field

from plantagent.config import PROJECT_ROOT

_TAGS = pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")

# Only real names are allowed: the 52 signals, and the process units used by list_tags.
Tag = Literal[tuple(_TAGS["tag"])]
ProcessUnit = Literal[tuple(dict.fromkeys(_TAGS["process_unit"]))]
FaultId = Annotated[int, Field(ge=1, le=15)]
Claim = Literal["above_normal", "below_normal", "top_contributor", "monitor_alarm", "doc_section"]


class Evidence(BaseModel):
    call_id: str = Field(pattern=r"^c\d+$", description="The call_id of the tool result this fact comes from, like 'c3'.")
    claim: Claim = Field(description=(
        "What the cited result shows. above_normal / below_normal: a compare_to_normal result gives this tag "
        "direction 'up' / 'down' (z_score >= 2 / <= -2). top_contributor: a top_contributors result lists this "
        "tag. monitor_alarm: a get_monitor_status result whose first_alarm_time is not null. doc_section: a "
        "search_docs result returned this section."))
    tag: Tag | None = Field(description="The signal, like 'xmeas_9', for above_normal, below_normal and "
                                        "top_contributor. null for monitor_alarm and doc_section.")
    section_id: str | None = Field(description="For doc_section only: the section_id, like "
                                               "'process_overview#the-reactor'. null otherwise.")
    detail: str = Field(description="One short sentence saying what this fact means for the diagnosis.")


class Diagnosis(BaseModel):
    evidence: list[Evidence] = Field(max_length=8, description=(
        "The facts behind the diagnosis, each taken from one tool result you received. Every one is "
        "checked against that result. At least one is needed when status is 'fault'."))
    key_variables: list[Tag] = Field(max_length=6, description="The signals that matter most for the diagnosis.")
    affected_unit: ProcessUnit | None = Field(description="The part of the plant where the problem seems to "
                                                          "start, or null if there is no fault or it is unclear.")
    status: Literal["no_fault", "fault", "inconclusive"] = Field(description=(
        "no_fault: the plant behaves normally. fault: something is wrong (with fault_id null if none of faults "
        "1 to 15 fits). inconclusive: the data does not allow a decision."))
    fault_id: FaultId | None = Field(description=(
        "The catalogue number (1 to 15) of the most likely fault. null if status is not 'fault', or if the "
        "fault matches none of faults 1 to 15."))
    ranked_candidates: list[FaultId] = Field(max_length=3, description=(
        "Up to 3 catalogue numbers, most likely first (the first one equal to fault_id when fault_id is set). "
        "Empty if no catalogue fault fits."))
    confidence: Literal["low", "medium", "high"]
    recommended_checks: list[str] = Field(max_length=3, description=(
        "Up to 3 things an operator could check on site to confirm the diagnosis. Recommendations only: "
        "nothing is changed in the plant."))
