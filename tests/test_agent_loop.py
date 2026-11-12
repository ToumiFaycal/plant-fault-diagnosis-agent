"""Tests for the agent loop, with a scripted fake model instead of Qwen3 and the server over the
made-up episode (no language model and no real data needed)."""

import asyncio
import json

from mcp import Client
from ollama import ChatResponse, Message

from plantagent.agent.loop import investigate, tools_for_ollama, write_report
from plantagent.agent.prompts import fault_catalogue, system_prompt
from plantagent.config import PROJECT_ROOT
from test_mcp_server import made_up_server  # the server over the made-up episode (now = 05:00)


def reply(*requests: tuple[str, dict], content: str = "") -> ChatResponse:
    """A model reply asking for these tools (none: it's ready to report)."""
    tool_calls = [Message.ToolCall(function=Message.ToolCall.Function(name=name, arguments=arguments))
                  for name, arguments in requests] or None
    return ChatResponse(message=Message(role="assistant", content=content, tool_calls=tool_calls),
                        prompt_eval_count=100, eval_count=10)


class ScriptedModel:
    """A fake model that gives the scripted replies in order (the last one again if it runs out),
    and remembers what it was shown."""

    def __init__(self, *replies: ChatResponse):
        self.replies, self.seen = list(replies), []

    async def __call__(self, messages, tools=None, format=None) -> ChatResponse:
        self.seen.append({"messages": list(messages), "tools": tools, "format": format})
        return self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]


def run(model: ScriptedModel, max_steps: int = 12):
    async def go():
        async with Client(made_up_server()) as client:
            return await investigate(client, model, "The plant monitor raised an alarm at 04:00. It is now 05:00.",
                                     max_steps)
    return asyncio.run(go())


def tool_messages(investigation) -> list[dict]:
    return [m for m in investigation.messages if isinstance(m, dict) and m["role"] == "tool"]


# --- The tools, as the model sees them ---

def test_the_seven_tools_are_described_for_ollama():
    async def listing():
        async with Client(made_up_server()) as client:
            return (await client.list_tools()).tools
    tools = tools_for_ollama(asyncio.run(listing()))
    assert len(tools) == 7 and all(tool["type"] == "function" for tool in tools)
    compare = next(tool["function"] for tool in tools if tool["function"]["name"] == "compare_to_normal")
    assert "z-score" in compare["description"]
    assert set(compare["parameters"]["properties"]) == {"tags", "window_start", "window_end"}


# --- The loop's heart (yours) ---

def test_the_requested_tools_run_and_their_results_go_back_to_the_model():
    model = ScriptedModel(reply(("get_episode_info", {}),
                                ("get_monitor_status", {"window_start": "03:00", "window_end": "04:00"})),
                          reply(content="I have enough evidence."))
    investigation = run(model)
    assert investigation.tool_calls == 2 and investigation.model_calls == 2
    assert {call_id: call.tool for call_id, call in investigation.calls.items()} == {
        "c1": "get_episode_info", "c2": "get_monitor_status"}
    answers = tool_messages(investigation)
    assert [m["tool_name"] for m in answers] == ["get_episode_info", "get_monitor_status"]
    assert json.loads(answers[1]["content"])["first_alarm_time"] == "03:39"
    # The second time, the model was shown the two results.
    assert len(model.seen[1]["messages"]) == len(model.seen[0]["messages"]) + 3  # its request + 2 results


def test_the_investigation_stops_when_the_model_asks_for_nothing():
    investigation = run(ScriptedModel(reply(content="The plant looks fine.")))
    assert (investigation.model_calls, investigation.tool_calls, investigation.stopped_by) == (1, 0, "model")


def test_the_investigation_stops_at_the_step_limit():
    investigation = run(ScriptedModel(reply(("get_episode_info", {}))), max_steps=3)  # never stops by itself
    assert (investigation.model_calls, investigation.tool_calls, investigation.stopped_by) == (3, 3, "step_limit")


def test_a_tool_error_goes_back_to_the_model_as_a_message():
    investigation = run(ScriptedModel(
        reply(("get_trend", {"tag": "xmeas_9", "window_start": "06:00", "window_end": "07:00"})),  # after now
        reply(content="Done.")))
    answer = tool_messages(investigation)[0]["content"]
    assert "after now" in answer
    assert investigation.calls == {}  # no receipt for a failed call: nothing to cite


def test_an_unknown_tool_goes_back_to_the_model_as_a_message():
    investigation = run(ScriptedModel(reply(("shut_down_the_plant", {})), reply(content="Done.")))
    assert "Unknown tool" in tool_messages(investigation)[0]["content"]
    assert investigation.stopped_by == "model"


def test_every_step_is_traced():
    investigation = run(ScriptedModel(reply(("get_episode_info", {})), reply(content="Done.")))
    assert [event["event"] for event in investigation.trace] == ["model", "tool", "model"]
    model_event, tool_event = investigation.trace[0], investigation.trace[1]
    assert model_event["asked_for"] == [{"tool": "get_episode_info", "arguments": {}}]
    assert (model_event["prompt_tokens"], model_event["output_tokens"]) == (100, 10)
    assert tool_event["call_id"] == "c1" and tool_event["is_error"] is False and "latency_s" in tool_event


# --- The final report ---

GOOD_REPORT = json.dumps({
    "evidence": [{"call_id": "c1", "claim": "monitor_alarm", "tag": None, "section_id": None, "detail": "Alarm."}],
    "key_variables": ["xmeas_9"], "affected_unit": "reactor", "status": "fault", "fault_id": 4,
    "ranked_candidates": [4], "confidence": "medium", "recommended_checks": []})


def test_the_report_is_asked_for_on_the_form_and_read_into_it():
    model = ScriptedModel(reply(content="Ready."), reply(content=GOOD_REPORT))
    investigation = run(model)
    report = asyncio.run(write_report(model, investigation))
    assert report.fault_id == 4 and report.evidence[0].claim == "monitor_alarm"
    last = model.seen[-1]
    assert last["format"]["title"] == "Diagnosis" and last["tools"] is None  # the form, and no tools
    assert investigation.trace[-1]["event"] == "report"


def test_a_report_that_does_not_fit_the_form_gives_none():
    model = ScriptedModel(reply(content="Ready."), reply(content='{"status": "probably fine"}'))
    investigation = run(model)
    assert asyncio.run(write_report(model, investigation)) is None
    assert "invalid" in investigation.trace[-1]


# --- What the model is told ---

def test_the_instructions_include_the_fault_catalogue_without_its_sources():
    catalogue = fault_catalogue()
    for fault in range(1, 16):
        assert f"## Fault {fault}:" in catalogue
    assert "Sources" not in catalogue and "temexd" not in catalogue
    assert catalogue in system_prompt()


def test_the_agent_code_never_mentions_the_answers():
    forbidden = ("labels_", "faultnumber", "simulationrun", "processed")
    for path in (PROJECT_ROOT / "src" / "plantagent" / "agent").glob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        assert not any(word in text for word in forbidden), f"{path.name} mentions an answer source"
