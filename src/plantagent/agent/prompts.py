"""The texts the model reads besides the tool results: its instructions at the start of an
investigation (the "system prompt"), the request for the final report at the end, and, if the
fact-checker found problems, the request to correct the report (its one second chance).

The instructions describe the job and the rules, not the answers: nothing here says which
signals go with which fault. The fault catalogue is included because the report must name a
catalogue number, and it describes causes only (see knowledge/fault_catalogue.md).

Version 2 (step 8.3): after the first trial, the instructions say more about *how* to work:
compare the top contributors to normal, what counts as an alarm, the four possible conclusions,
when to be confident, and which result each kind of evidence needs.
"""

import json

from plantagent.agent.diagnosis import Diagnosis
from plantagent.config import load_config
from plantagent.docsearch import knowledge_sections


def fault_catalogue() -> str:
    """The catalogue's sections (kinds of faults, faults 1 to 15, faults 16 to 20), without its sources."""
    return "\n\n".join(f"## {section.title}\n{section.text}" for section in knowledge_sections()
                       if section.section_id.startswith("fault_catalogue#"))


def system_prompt() -> str:
    in_a_row = load_config()["monitor"]["alarm_after_consecutive"]
    return f"""You investigate a problem report in a simulated chemical plant, the Tennessee Eastman process. \
You can see the plant only through your tools, and you cannot change anything in it.

How to work:
- Start with get_episode_info.
- Find out what the plant monitor saw: get_monitor_status, then top_contributors.
- Then compare the top contributors to normal with compare_to_normal (it takes several tags at once). A big \
contributor is not always far from normal: only compare_to_normal tells you whether a signal is above or below \
normal.
- Use get_trend to see how a signal moved, list_tags to find signal names, and search_docs to read how the \
plant works and what each fault changes.
- You may call several tools at each turn. When you have enough evidence, reply without calling any tool: \
you will then be asked for your final report.

How to read the monitor:
- The monitor raises an alarm only after {in_a_row} moments in a row above a limit. In a get_monitor_status \
result, first_alarm_time gives the alarm. If it is null, there was no alarm in that window, even if a score \
went above its limit for a moment.

How to conclude:
- no_fault: the monitor shows no alarm and no signal is far from normal.
- fault with a fault_id: the evidence points to one fault of the catalogue below.
- fault with fault_id null: the plant is clearly abnormal, but none of faults 1 to 15 fits.
- inconclusive: something may be wrong, but the evidence does not allow a decision.
- Use high confidence only when several pieces of evidence agree and one catalogue fault fits clearly better \
than the others.

Rules:
- Times are HH:MM counted from the start of the run. Nothing after "now" exists.
- Never calculate numbers yourself: use the numbers in the tool results.
- Every tool result has a call_id. Your report must cite them, and every citation is checked against the \
result it names.

The faults that can be switched on in this plant (the fault catalogue):

{fault_catalogue()}"""


def report_request() -> str:
    schema = json.dumps(Diagnosis.model_json_schema(), ensure_ascii=False)
    return f"""Stop investigating now and write your final report. Answer with JSON only, following this schema:

{schema}

Each piece of evidence must cite the call_id of a tool result from this conversation, and is checked against \
that result. Which result each claim needs:
- above_normal / below_normal: a compare_to_normal result in which that tag's direction is "up" / "down".
- top_contributor: a top_contributors result that lists that tag.
- monitor_alarm: a get_monitor_status result whose first_alarm_time is not null.
- doc_section: a search_docs result that returned that section."""


def fix_request(problems: list[str]) -> str:
    """The second chance: the fact-checker's problems, and the request for a corrected report."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return f"""A fact-checker compared your report with the tool results it cites and found these problems:

{listed}

Write your whole report again, as JSON following the same schema. For each problem, either cite a tool \
result that really supports the claim, or remove that piece of evidence. You cannot call tools any more: use \
only the results already in this conversation. If the evidence that remains no longer supports your \
conclusion, change the conclusion or lower your confidence."""
