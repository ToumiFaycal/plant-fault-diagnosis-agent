"""The texts the model reads besides the tool results: its instructions at the start of an
investigation (the "system prompt"), the request for the final report at the end, and, if the
fact-checker found problems, the request to correct the report (its one second chance).

The instructions describe the job and the rules, not the answers: nothing here says which
signals go with which fault. The fault catalogue is included because the report must name a
catalogue number, and it describes causes only (see knowledge/fault_catalogue.md).
"""

import json

from plantagent.agent.diagnosis import Diagnosis
from plantagent.docsearch import knowledge_sections


def fault_catalogue() -> str:
    """The catalogue's sections (kinds of faults, faults 1 to 15, faults 16 to 20), without its sources."""
    return "\n\n".join(f"## {section.title}\n{section.text}" for section in knowledge_sections()
                       if section.section_id.startswith("fault_catalogue#"))


def system_prompt() -> str:
    return f"""You investigate a problem report in a simulated chemical plant, the Tennessee Eastman process. \
You can see the plant only through your tools, and you cannot change anything in it.

How to work:
- Start with get_episode_info.
- Find out what the plant monitor saw (get_monitor_status, top_contributors), then check the signals that \
matter (compare_to_normal, get_trend). Use list_tags to find signal names and search_docs to read how the \
plant works.
- You may call several tools at each turn. When you have enough evidence, reply without calling any tool: \
you will then be asked for your final report.
- Your conclusion can be that the plant is normal, that it has a fault, or that the data does not allow a \
decision.

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
that result."""


def fix_request(problems: list[str]) -> str:
    """The second chance: the fact-checker's problems, and the request for a corrected report."""
    listed = "\n".join(f"- {problem}" for problem in problems)
    return f"""A fact-checker compared your report with the tool results it cites and found these problems:

{listed}

Write your whole report again, as JSON following the same schema. For each problem, either cite a tool \
result that really supports the claim, or remove that piece of evidence. You cannot call tools any more: use \
only the results already in this conversation. If the evidence that remains no longer supports your \
conclusion, change the conclusion or lower your confidence."""
