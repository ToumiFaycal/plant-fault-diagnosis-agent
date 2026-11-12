"""Tests for the second chance: a report that fails the fact-check goes back to the model once,
with the problems, and the outcome is "passed", "fixed" or "verification_failed".

No language model: the scripted fake model from test_agent_loop.py hands in prepared reports.
"""

import asyncio
import json

from plantagent.agent.loop import Investigation
from plantagent.agent.second_chance import NOT_ON_FORM, report_with_second_chance
from plantagent.agent.verifier import ToolCall
from test_agent_loop import ScriptedModel, reply


def investigation_so_far() -> Investigation:
    """An investigation that has made one tool call: c1, the monitor in alarm since 08:09."""
    calls = {"c1": ToolCall("c1", "get_monitor_status", {}, {"first_alarm_time": "08:09", "moments_in_alarm": 21})}
    return Investigation(messages=[{"role": "system", "content": "You investigate..."}], calls=calls)


def report_citing(call_id: str) -> str:
    """A report (as the model writes it: JSON text) whose only evidence is "the monitor alarmed", citing call_id."""
    return json.dumps({
        "evidence": [{"call_id": call_id, "claim": "monitor_alarm", "tag": None, "section_id": None,
                      "detail": "The monitor alarmed."}],
        "key_variables": [], "affected_unit": None, "status": "fault", "fault_id": None,
        "ranked_candidates": [], "confidence": "low", "recommended_checks": []})


GOOD = report_citing("c1")  # c1 exists and shows an alarm: holds
BAD = report_citing("c9")   # c9 was never issued: fails


def hand_in(*reports: str):
    """The fake model hands in these reports, in order (the last one again if asked for more)."""
    model = ScriptedModel(*[reply(content=report) for report in reports])
    investigation = investigation_so_far()
    checked = asyncio.run(report_with_second_chance(model, investigation))
    return checked, model, investigation


def test_a_report_that_holds_is_kept_without_a_second_chance():
    checked, model, _ = hand_in(GOOD)
    assert checked.outcome == "passed"
    assert len(model.seen) == 1  # the report was asked for once, and that's all
    assert checked.second_check is None
    assert checked.report.evidence[0].call_id == "c1"


def test_a_corrected_report_that_holds_counts_as_fixed():
    checked, model, _ = hand_in(BAD, GOOD)
    assert checked.outcome == "fixed"
    assert len(model.seen) == 2
    assert checked.first_check.failed_items == 1 and checked.second_check.passed
    assert checked.report.evidence[0].call_id == "c1"  # we keep the corrected report


def test_a_report_that_still_fails_is_verification_failed():
    checked, model, _ = hand_in(BAD, BAD)  # the fake model would hand in BAD forever if asked
    assert checked.outcome == "verification_failed"
    assert len(model.seen) == 2  # one second chance only, never a third
    assert not checked.second_check.passed


def test_the_second_chance_shows_the_problems_and_allows_no_tools():
    _, model, _ = hand_in(BAD, GOOD)
    second = model.seen[1]
    request = second["messages"][-1]["content"]  # the last message the model read: the problems
    assert "fact-checker" in request and "c9" in request
    assert second["tools"] is None  # no new investigation, only a corrected report
    assert second["format"]["title"] == "Diagnosis"  # on the same form


def test_a_report_off_the_form_also_gets_its_second_chance():
    checked, _, _ = hand_in('{"status": "probably fine"}', GOOD)
    assert checked.first_check.problems == [NOT_ON_FORM]
    assert checked.outcome == "fixed"


def test_the_trace_numbers_the_two_reports():
    _, _, investigation = hand_in(BAD, GOOD)
    assert [event["attempt"] for event in investigation.trace if event["event"] == "report"] == [1, 2]
