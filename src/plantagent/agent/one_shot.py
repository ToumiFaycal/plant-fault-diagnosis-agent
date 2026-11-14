"""Baseline B3: the same model, one question, no tools (step 9.2).

Why it exists: to find out whether the agent's investigation is worth its time. B3 gets, in one
message, what the plant monitor offers at once, as the FaultExplainer study (Purdue University,
2024) did: the alarm, the signals that contribute most, and the fault catalogue. It can't ask for
anything else. If B3 scores as well as the agent, the tools and the investigation add nothing.

What B3 is given, for the last hour before "now" (for an alarm episode: the hour since the alarm):
  c1  get_monitor_status                 the two scores against their limits, the first alarm
  c2  top_contributors, statistic T2     the 6 signals carrying most of the "strange amount" score
  c3  top_contributors, statistic SPE    the 6 signals carrying most of the "strange pattern" score
They come from the same plant server as the agent's tools, so they're real results with real
call_ids: B3's report goes through the same fact-checker and gets the same one second chance.
Everything else is the same as for the agent too: model, settings, the rules on how to read the
monitor and how to conclude, the fault catalogue, the report form.

Run it (needs Ollama, the saved monitor and the search index, like the agent):
    python -m plantagent.agent.one_shot --trial
    python -m plantagent.agent.one_shot --episodes ep_f6f8d79c
The traces go to results/traces/<run_id>/ in the agent's format, so the grader reads both alike:
    python -m plantagent.evaluation.grade results/traces/<run_id>
"""

import argparse
import asyncio
import json
import logging
import time
from collections.abc import Callable
from datetime import datetime

from mcp import Client

from plantagent.agent.loop import SHORT, Chat, Investigation, ollama_chat
from plantagent.agent.prompts import one_shot_prompt
from plantagent.agent.run import episode_entry, print_summary, print_table, save_episode, show, show_memory
from plantagent.agent.second_chance import report_with_second_chance
from plantagent.agent.verifier import ToolCall
from plantagent.config import load_config
from plantagent.docsearch import index_path, knowledge_sections, load_index
from plantagent.episodes.build import MINUTES_PER_SAMPLE, sample_time
from plantagent.mcp_server.episode import load_episode
from plantagent.mcp_server.server import build_server
from plantagent.monitor.saved import load_monitor, monitor_path

# The results B3 is given: (tool, arguments besides the time window).
GIVEN = (("get_monitor_status", {}),
         ("top_contributors", {"k": 6, "statistic": "T2"}),
         ("top_contributors", {"k": 6, "statistic": "SPE"}))


def last_hour(now_sample: int, minutes: int) -> dict:
    """The time window B3 is shown: the `minutes` before now, as the tools expect it."""
    first = max(now_sample - minutes // MINUTES_PER_SAMPLE, 1)
    return {"window_start": sample_time(first), "window_end": sample_time(now_sample)}


async def prepare(client: Client, trigger_message: str, now_sample: int, minutes: int,
                  log: Callable[[dict], None] = lambda event: None) -> Investigation:
    """B3's whole "investigation": the three results it is given, and the message that hands them
    over. The model hasn't been called yet; next comes the report request, as for the agent."""
    window = last_hour(now_sample, minutes)
    investigation = Investigation(messages=[{"role": "system", "content": one_shot_prompt()}], log=log)
    investigation.stopped_by = "one_shot"  # there is no investigation to stop
    parts = [trigger_message,
             f"What the plant monitor saw over the last hour, from {window['window_start']} to {window['window_end']}:"]
    for tool, extra in GIVEN:
        arguments = {**window, **extra}
        result = await client.call_tool(tool, arguments)
        if result.is_error:
            raise RuntimeError(f"{tool} failed: {result.content[0].text}")
        content = result.structured_content
        investigation.calls[content["call_id"]] = ToolCall(content["call_id"], tool, arguments, content)
        text = json.dumps(content, ensure_ascii=False)
        investigation.record({"event": "given", "tool": tool, "arguments": arguments,
                              "call_id": content["call_id"], "result": text[:SHORT]})
        parts.append(f"Result {content['call_id']} ({tool}):\n{text}")
    investigation.messages.append({"role": "user", "content": "\n\n".join(parts)})
    return investigation


async def run_episode(name: str, split: str, chat: Chat, run_id: str) -> dict:
    config = load_config()
    entry = episode_entry(name, split)
    print(f"Episode {name} (B3, one question, no tools): {entry['trigger_message']}\n")
    started = time.perf_counter()

    episode, monitor = load_episode(name, split), load_monitor(monitor_path())
    docs = load_index(index_path(), knowledge_sections())  # the server needs it; B3 never searches
    async with Client(build_server(episode, monitor, docs)) as client:  # in memory: no separate program
        investigation = await prepare(client, entry["trigger_message"], episode.now_sample,
                                      config["episodes"]["investigate_after_minutes"], show)
    checked = await report_with_second_chance(chat, investigation)
    seconds = round(time.perf_counter() - started, 1)
    return save_episode("B3", name, split, run_id, entry["trigger_message"], investigation, checked, seconds)


async def run_episodes(names: list[str], chat: Chat, run_id: str) -> list[dict]:
    summaries = []
    for number, name in enumerate(names, start=1):
        if len(names) > 1:
            print(f"\n######## Episode {number} of {len(names)} ########")
        summary = await run_episode(name, "dev", chat, run_id)
        print_summary(summary)
        summaries.append(summary)
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline B3: one question to the model, no tools.")
    parser.add_argument("--episodes", nargs="+", default=["ep_f6f8d79c"], help="episode names from episodes/dev.jsonl")
    parser.add_argument("--trial", action="store_true", help="run the trial episodes listed in config.toml ([agent])")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_B3",
                        help="folder name for the traces (default: date and time, then _B3)")
    arguments = parser.parse_args()
    logging.getLogger("httpx").setLevel(logging.WARNING)  # no line per request to Ollama
    config = load_config()
    if not (monitor_path().exists() and index_path().exists()):
        raise SystemExit("Needs the saved monitor and the search index: python -m plantagent.monitor.saved, "
                         "then python -m plantagent.docsearch.")
    names = config["agent"]["trial_episodes"] if arguments.trial else arguments.episodes
    summaries = asyncio.run(run_episodes(names, ollama_chat(config["llm"]), arguments.run_id))
    if len(summaries) > 1:
        print_table(summaries)
    show_memory()


if __name__ == "__main__":
    main()
