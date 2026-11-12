"""The agent loop: the model investigates one episode by asking for tools, until it has enough.

The picture: a doctor (the model) and a lab (the plant-historian server). The doctor can't run
tests; it writes request slips (tool calls). This code is the nurse in between: it carries each
slip to the lab, brings the result back into the conversation, and writes everything down in the
trace. Round after round:

    ask the model -> it asked for tools?  yes -> run them, add their results, ask again
                                          no  -> the investigation is over

At most `max_steps` rounds; then the model is asked for its final report, as a Diagnosis form.

The model is passed in as a function (`chat`), so tests can replace Qwen3 with a scripted fake,
and the tools come from an MCP client, so tests can use the server over a made-up episode.
"""

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from mcp import Client
from ollama import ChatResponse
from pydantic import ValidationError

from plantagent.agent.diagnosis import Diagnosis
from plantagent.agent.prompts import report_request, system_prompt
from plantagent.agent.verifier import ToolCall

# The model: messages (and optionally tools or a form to fill) in, one reply out.
Chat = Callable[..., Awaitable[ChatResponse]]
SHORT = 300  # characters of each text kept in the trace


@dataclass
class Investigation:
    messages: list  # the whole conversation, as the model sees it
    calls: dict[str, ToolCall] = field(default_factory=dict)  # the successful tool calls, by call_id
    trace: list[dict] = field(default_factory=list)  # one entry per event, saved to the trace file
    model_calls: int = 0
    tool_calls: int = 0
    stopped_by: str = "step_limit"  # or "model": it stopped asking for tools by itself
    log: Callable[[dict], None] = field(default=lambda event: None, repr=False)  # shows events as they happen

    def record(self, event: dict) -> None:
        self.trace.append(event)
        self.log(event)


def tools_for_ollama(mcp_tools) -> list[dict]:
    """The server's tools, described the way Ollama expects: name, description, and the JSON
    schema of the arguments, all taken from the MCP tool list."""
    return [{"type": "function",
             "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema}}
            for tool in mcp_tools]


async def ask_model(chat: Chat, investigation: Investigation, tools: list[dict], step: int) -> ChatResponse:
    """One model call: the whole conversation in, one reply out (text, tool requests or both)."""
    started = time.perf_counter()
    reply = await chat(investigation.messages, tools=tools)
    investigation.messages.append(reply.message)
    investigation.model_calls += 1
    investigation.record({
        "event": "model", "step": step, "latency_s": round(time.perf_counter() - started, 2),
        "load_s": round((reply.load_duration or 0) / 1e9, 2),  # time spent loading the model first
        "prompt_tokens": reply.prompt_eval_count, "output_tokens": reply.eval_count,
        "said": (reply.message.content or "")[:SHORT],
        "asked_for": [{"tool": request.function.name, "arguments": dict(request.function.arguments)}
                      for request in reply.message.tool_calls or []],
    })
    return reply


async def run_tool(client: Client, request, investigation: Investigation, step: int) -> str:
    """Run one tool the model asked for, and return the text the model will read: the result as
    JSON, or the error message (so the model can correct its request)."""
    name, arguments = request.function.name, dict(request.function.arguments)
    started = time.perf_counter()
    result = await client.call_tool(name, arguments)
    investigation.tool_calls += 1
    if result.is_error:
        answer, call_id = result.content[0].text, None
    else:
        answer = json.dumps(result.structured_content, ensure_ascii=False)
        call_id = result.structured_content["call_id"]
        investigation.calls[call_id] = ToolCall(call_id, name, arguments, result.structured_content)
    investigation.record({
        "event": "tool", "step": step, "tool": name, "arguments": arguments, "call_id": call_id,
        "is_error": result.is_error, "latency_s": round(time.perf_counter() - started, 3),
        "result": answer[:SHORT],
    })
    return answer


async def investigate(client: Client, chat: Chat, trigger_message: str, max_steps: int,
                      log: Callable[[dict], None] = lambda event: None) -> Investigation:
    """The investigation of one episode, up to the moment the final report is requested."""
    tools = tools_for_ollama((await client.list_tools()).tools)
    investigation = Investigation(messages=[{"role": "system", "content": system_prompt()},
                                            {"role": "user", "content": trigger_message}], log=log)
    for step in range(1, max_steps + 1):
        reply = await ask_model(chat, investigation, tools, step)
        requests = reply.message.tool_calls or []  # the model's request slips (an empty list if none)

        if not requests:
            investigation.stopped_by = "model"
            break

        for request in requests:
            answer = await run_tool(client, request, investigation, step)
            investigation.messages.append({"role": "tool", "tool_name": request.function.name, "content": answer})
    return investigation


async def write_report(chat: Chat, investigation: Investigation, request: str | None = None) -> Diagnosis | None:
    """Ask for the final report, shaped by the Diagnosis form. None if it doesn't fit the form.
    `request` is the message that asks for it: the usual report request, or the fact-checker's
    problems for a corrected report (see second_chance.py)."""
    attempt = 1 + sum(event["event"] == "report" for event in investigation.trace)  # 2 = the second chance
    investigation.messages.append({"role": "user", "content": request or report_request()})
    started = time.perf_counter()
    reply = await chat(investigation.messages, format=Diagnosis.model_json_schema())  # no tools: report only
    investigation.messages.append(reply.message)
    investigation.model_calls += 1
    event = {"event": "report", "attempt": attempt, "latency_s": round(time.perf_counter() - started, 2),
             "load_s": round((reply.load_duration or 0) / 1e9, 2),
             "prompt_tokens": reply.prompt_eval_count, "output_tokens": reply.eval_count,
             "report": reply.message.content}
    try:
        report = Diagnosis.model_validate_json(reply.message.content)
    except ValidationError as problem:
        event["invalid"] = str(problem)[:1000]
        report = None
    investigation.record(event)
    return report


def ollama_chat(settings: dict[str, Any]) -> Chat:
    """The real model: Qwen3 through Ollama, with the settings from config.toml ([llm])."""
    import ollama

    client = ollama.AsyncClient()

    async def chat(messages: list, tools: list[dict] | None = None, format: dict | None = None) -> ChatResponse:
        return await client.chat(
            model=settings["model"], messages=messages, tools=tools, format=format, think=settings["think"],
            options={"num_ctx": settings["num_ctx"], "temperature": settings["temperature"], "seed": settings["seed"]},
        )

    return chat
