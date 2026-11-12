"""Tests for the diagnosis form and the fact-checker (no language model needed: the tool results
and the reports are made up)."""

import asyncio

import pytest
from mcp import Client
from pydantic import ValidationError

from plantagent.agent.diagnosis import Diagnosis, Evidence
from plantagent.agent.verifier import ToolCall, check_evidence, section_was_returned, verify, z_supports_claim
from plantagent.mcp_server.tools import PROCESS_UNITS
from test_mcp_server import made_up_server  # the server over the made-up episode, monitor and documents

# A made-up investigation: five results, shaped like the real tools' results (only the fields used).
CALLS = {
    "c1": ToolCall("c1", "get_monitor_status", {}, {"first_alarm_time": "08:09", "moments_in_alarm": 21}),
    "c2": ToolCall("c2", "top_contributors", {}, {"contributors": [{"rank": 1, "tag": "xmv_10"},
                                                                   {"rank": 2, "tag": "xmeas_9"}]}),
    "c3": ToolCall("c3", "compare_to_normal", {}, {"signals": [{"tag": "xmv_10", "z_score": 7.0},
                                                               {"tag": "xmeas_9", "z_score": -0.9},
                                                               {"tag": "xmeas_21", "z_score": -2.0}]}),
    "c4": ToolCall("c4", "search_docs", {}, {"sections": [{"section_id": "fault_catalogue#fault-4"},
                                                          {"section_id": "process_overview#the-reactor"}]}),
    "c5": ToolCall("c5", "get_monitor_status", {}, {"first_alarm_time": None, "moments_in_alarm": 0}),
}


def evidence(call_id: str, claim: str, tag: str | None = None, section_id: str | None = None) -> Evidence:
    return Evidence(call_id=call_id, claim=claim, tag=tag, section_id=section_id, detail="...")


def report(status: str, items: list[Evidence]) -> Diagnosis:
    return Diagnosis(evidence=items, key_variables=[], affected_unit=None, status=status, fault_id=None,
                     ranked_candidates=[], confidence="low", recommended_checks=[])


# --- The form ---

def test_the_form_accepts_a_complete_report():
    good = Diagnosis.model_validate({
        "evidence": [{"call_id": "c3", "claim": "above_normal", "tag": "xmv_10", "section_id": None,
                      "detail": "The reactor cooling valve is far above normal."}],
        "key_variables": ["xmv_10", "xmeas_9"], "affected_unit": "reactor", "status": "fault", "fault_id": 4,
        "ranked_candidates": [4, 11, 14], "confidence": "medium", "recommended_checks": ["Check the valve."]})
    assert good.fault_id == 4 and good.evidence[0].tag == "xmv_10"


@pytest.mark.parametrize("change", [
    {"fault_id": 16},                       # only 1 to 15 exist in the catalogue
    {"key_variables": ["xmeas_99"]},        # not a real signal
    {"ranked_candidates": [1, 2, 3, 4]},    # at most 3
    {"affected_unit": "boiler"},            # not a process unit of this plant
    {"status": "maybe"},
])
def test_the_form_refuses_impossible_answers(change):
    answer = {"evidence": [], "key_variables": [], "affected_unit": None, "status": "inconclusive",
              "fault_id": None, "ranked_candidates": [], "confidence": "low", "recommended_checks": []}
    with pytest.raises(ValidationError):
        Diagnosis.model_validate(answer | change)


def test_the_form_uses_the_same_process_units_as_the_server():
    schema = Diagnosis.model_json_schema()
    assert set(schema["properties"]["affected_unit"]["anyOf"][0]["enum"]) == set(PROCESS_UNITS)


def test_the_evidence_comes_first_in_the_form():
    assert list(Diagnosis.model_json_schema()["properties"])[0] == "evidence"


# --- Your two checks ---

def test_z_supports_claim():
    assert z_supports_claim("above_normal", 7.0)
    assert not z_supports_claim("above_normal", 0.02)   # a big contributor isn't always above normal
    assert z_supports_claim("below_normal", -2.0)       # exactly 2 wobbles below counts
    assert not z_supports_claim("below_normal", 3.0)
    assert not z_supports_claim("above_normal", -3.0)   # far from normal, but in the other direction


def test_section_was_returned():
    assert section_was_returned(CALLS["c4"].result, "fault_catalogue#fault-4")
    assert not section_was_returned(CALLS["c4"].result, "fault_catalogue#fault-6")


# --- Each kind of evidence ---

def test_good_evidence_holds():
    for item in [evidence("c1", "monitor_alarm"), evidence("c2", "top_contributor", tag="xmv_10"),
                 evidence("c3", "above_normal", tag="xmv_10"), evidence("c3", "below_normal", tag="xmeas_21"),
                 evidence("c4", "doc_section", section_id="process_overview#the-reactor")]:
        assert check_evidence(item, CALLS) == [], item


def test_an_invented_call_id_fails():
    problems = check_evidence(evidence("c9", "above_normal", tag="xmv_10"), CALLS)
    assert len(problems) == 1 and "c9" in problems[0]


def test_citing_the_wrong_tool_fails():
    problems = check_evidence(evidence("c2", "above_normal", tag="xmv_10"), CALLS)  # c2 is top_contributors
    assert len(problems) == 1 and "compare_to_normal" in problems[0]


def test_a_direction_the_z_score_does_not_support_fails():
    problems = check_evidence(evidence("c3", "above_normal", tag="xmeas_9"), CALLS)  # z = -0.9
    assert len(problems) == 1 and "-0.9" in problems[0]


def test_a_tag_missing_from_the_result_fails():
    assert check_evidence(evidence("c3", "above_normal", tag="xmeas_1"), CALLS) != []
    assert check_evidence(evidence("c2", "top_contributor", tag="xmeas_1"), CALLS) != []
    assert check_evidence(evidence("c2", "top_contributor"), CALLS) != []  # no tag at all


def test_a_section_that_was_not_returned_fails():
    assert check_evidence(evidence("c4", "doc_section", section_id="fault_catalogue#fault-6"), CALLS) != []


def test_an_alarm_claim_on_a_quiet_window_fails():
    assert check_evidence(evidence("c5", "monitor_alarm"), CALLS) != []


# --- The whole report ---

def test_a_fault_needs_evidence_but_no_fault_does_not():
    assert not verify(report("fault", []), CALLS).passed
    assert verify(report("no_fault", []), CALLS).passed


def test_verify_counts_failed_pieces_of_evidence():
    result = verify(report("fault", [evidence("c3", "above_normal", tag="xmv_10"),     # holds
                                     evidence("c9", "monitor_alarm"),                    # invented receipt
                                     evidence("c3", "above_normal", tag="xmeas_9")]),    # wrong direction
                    CALLS)
    assert (result.evidence_items, result.failed_items) == (3, 2)
    assert not result.passed
    assert result.problems[0].startswith("evidence 2 (monitor_alarm, c9)")


def test_the_checker_reads_real_tool_results():
    # Real results from the server (made-up episode): the field names the checker reads must match.
    asked = [("get_monitor_status", {"window_start": "03:00", "window_end": "04:00"}),       # c1: alarm at 03:39
             ("top_contributors", {"window_start": "04:00", "window_end": "05:00", "k": 2}),   # c2: xmeas_1, xmeas_2
             ("compare_to_normal", {"tags": ["xmeas_9"], "window_start": "04:00", "window_end": "05:00"}),  # c3: z +4
             ("compare_to_normal", {"tags": ["xmeas_9"], "window_start": "01:00", "window_end": "02:00"}),  # c4: z -2
             ("search_docs", {"query": "mostly the reactor"})]                                   # c5: doc#reactor

    async def investigate() -> dict[str, ToolCall]:
        calls = {}
        async with Client(made_up_server()) as client:
            for tool, arguments in asked:
                result = (await client.call_tool(tool, arguments)).structured_content
                calls[result["call_id"]] = ToolCall(result["call_id"], tool, arguments, result)
        return calls

    calls = asyncio.run(investigate())
    good = report("fault", [evidence("c1", "monitor_alarm"), evidence("c2", "top_contributor", tag="xmeas_1"),
                            evidence("c3", "above_normal", tag="xmeas_9"), evidence("c4", "below_normal", tag="xmeas_9"),
                            evidence("c5", "doc_section", section_id="doc#reactor")])
    assert verify(good, calls).problems == []
    bad = report("fault", [evidence("c3", "below_normal", tag="xmeas_9"), evidence("c5", "doc_section",
                                                                                   section_id="doc#stripper")])
    assert verify(bad, calls).failed_items == 2
