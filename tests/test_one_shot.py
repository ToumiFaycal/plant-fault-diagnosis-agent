"""Tests for baseline B3 (one question, no tools), with the made-up episode (now = 05:00, the
monitor in alarm since 03:39) and the scripted fake model instead of Qwen3."""

import asyncio
import json

from mcp import Client

from plantagent.agent.one_shot import last_hour, prepare
from plantagent.agent.prompts import HOW_TO_CONCLUDE, fault_catalogue, how_to_read_the_monitor, one_shot_prompt, system_prompt
from plantagent.agent.second_chance import report_with_second_chance
from test_agent_loop import GOOD_REPORT, ScriptedModel, reply
from test_mcp_server import made_up_server

TRIGGER = "The plant monitor raised an alarm at 04:00. It is now 05:00."


def given():
    """B3's prepared conversation on the made-up episode: the three results, no model call yet."""
    async def go():
        async with Client(made_up_server()) as client:
            return await prepare(client, TRIGGER, now_sample=100, minutes=60)
    return asyncio.run(go())


def test_the_window_is_the_last_hour_and_never_starts_before_the_run():
    assert last_hour(183, 60) == {"window_start": "08:09", "window_end": "09:09"}  # an alarm at 08:09, now 09:09
    assert last_hour(10, 60) == {"window_start": "00:03", "window_end": "00:30"}   # only 10 samples exist


def test_b3_is_given_the_monitor_status_and_both_top_six():
    investigation = given()
    assert [(c.call_id, c.tool, c.arguments.get("statistic")) for c in investigation.calls.values()] == [
        ("c1", "get_monitor_status", None), ("c2", "top_contributors", "T2"), ("c3", "top_contributors", "SPE")]
    for call in investigation.calls.values():
        assert (call.arguments["window_start"], call.arguments["window_end"]) == ("04:00", "05:00")
    assert len(investigation.calls["c2"].result["contributors"]) == 6
    question = investigation.messages[-1]["content"]
    assert TRIGGER in question and "Result c1" in question and "Result c3" in question
    assert (investigation.model_calls, investigation.tool_calls) == (0, 0)  # it asked for nothing


def test_b3_writes_its_report_without_tools_and_it_is_fact_checked():
    model = ScriptedModel(reply(content=GOOD_REPORT))  # cites c1 as the alarm: true, it's on since 03:39
    investigation = given()
    checked = asyncio.run(report_with_second_chance(model, investigation))
    assert checked.outcome == "passed"
    assert len(model.seen) == 1  # one question, one answer
    assert model.seen[0]["tools"] is None and model.seen[0]["format"]["title"] == "Diagnosis"
    assert model.seen[0]["messages"][0]["content"] == one_shot_prompt()


def test_a_b3_report_citing_a_result_it_was_not_given_gets_its_second_chance():
    invented = json.loads(GOOD_REPORT)
    invented["evidence"][0]["call_id"] = "c4"  # B3 was given c1 to c3 only
    model = ScriptedModel(reply(content=json.dumps(invented)), reply(content=GOOD_REPORT))
    checked = asyncio.run(report_with_second_chance(model, given()))
    assert checked.outcome == "fixed"
    assert "c4" in model.seen[1]["messages"][-1]["content"]  # the fact-checker's problem, shown to the model


def test_b3_and_the_agent_share_the_rules_and_the_catalogue():
    for shared in (how_to_read_the_monitor(), HOW_TO_CONCLUDE, fault_catalogue()):
        assert shared in one_shot_prompt() and shared in system_prompt()
    assert "search_docs" not in one_shot_prompt() and "compare_to_normal" not in one_shot_prompt()
