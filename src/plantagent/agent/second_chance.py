"""The final report, fact-checked, with one second chance.

The picture: an exam handed back. The model writes its report and the fact-checker checks every
piece of evidence. If everything holds, we keep the report. If not, the model gets the list of
problems ("evidence 4 cites a trend, but a top_contributor claim must cite top_contributors") and
ONE chance to hand in a corrected report. It can't call tools any more: it can only fix or remove
evidence using the results it already has. The corrected report is checked too.

    first report --check--> holds?  yes -> keep it                            ("passed")
                                    no  -> problems back, corrected report
                                           --check--> holds?  yes -> keep it  ("fixed")
                                                              no  -> give up  ("verification_failed")

Why only one chance: each extra report costs about 40 s, and if the exact list of problems isn't
enough for the model to fix them, more rounds would mostly hide the weakness. "passed" and
"fixed" are counted separately, so the results show how much the second chance helps.
A report that doesn't even fit the Diagnosis form gets the same second chance, with one problem
saying so.
"""

from dataclasses import dataclass

from plantagent.agent.diagnosis import Diagnosis
from plantagent.agent.loop import Chat, Investigation, write_report
from plantagent.agent.prompts import fix_request
from plantagent.agent.verifier import ToolCall, Verification, verify

NOT_ON_FORM = ("your report did not fit the Diagnosis form: answer with JSON only, following the schema "
               "exactly (only the allowed values, at most 8 pieces of evidence).")


@dataclass
class CheckedReport:
    report: Diagnosis | None  # the report we keep: the corrected one if there was a second chance
    outcome: str  # "passed", "fixed" or "verification_failed"
    first_check: Verification  # the fact-check of the first report
    second_check: Verification | None = None  # the fact-check of the corrected report, if one was asked for


def check_report(report: Diagnosis | None, calls: dict[str, ToolCall]) -> Verification:
    """The fact-check of a report, or a single problem if the report didn't fit the form."""
    if report is None:
        return Verification(evidence_items=0, failed_items=0, problems=[NOT_ON_FORM])
    return verify(report, calls)


async def report_with_second_chance(chat: Chat, investigation: Investigation) -> CheckedReport:
    """Ask for the final report, check it, and if it fails, give the model one chance to correct it."""
    report = await write_report(chat, investigation)
    first_check = check_report(report, investigation.calls)

    if first_check.passed:
        return CheckedReport(report, "passed", first_check)

    corrected = await write_report(chat, investigation, fix_request(first_check.problems))  # the one second chance
    second_check = check_report(corrected, investigation.calls)

    if second_check.passed:
        return CheckedReport(corrected, "fixed", first_check, second_check)
    else:
        return CheckedReport(corrected, "verification_failed", first_check, second_check)
