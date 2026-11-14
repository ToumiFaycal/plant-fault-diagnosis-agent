"""Run the agent on development episodes, from start to finish, and show every step.

    python -m plantagent.agent                                   (the example episode ep_f6f8d79c)
    python -m plantagent.agent --episodes ep_3f9a1c2e ep_0b7d4e11  (any episodes from episodes/dev.jsonl)
    python -m plantagent.agent --trial                           (the trial episodes listed in config.toml)

What happens, for each episode: the plant-historian server is started for the episode (a
separate program, over stdio), Qwen3 investigates through its tools and writes its report on the
Diagnosis form, the fact-checker checks every piece of evidence, and if something fails, the
model gets one chance to correct its report. Everything is saved to
results/traces/<run_id>/<episode>.jsonl. Needs Ollama running, and the saved monitor and search
index (python -m plantagent.monitor.saved, python -m plantagent.docsearch).

This program never sees the answers: it shows what the agent concluded, not whether it was right.
Grading is a separate step.
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

from mcp import Client, StdioServerParameters

from plantagent.agent.loop import Chat, Investigation, investigate, ollama_chat
from plantagent.agent.second_chance import CheckedReport, report_with_second_chance
from plantagent.agent.verifier import Verification
from plantagent.config import PROJECT_ROOT, load_config
from plantagent.results_log import git_commit

EXAMPLE_EPISODE = "ep_f6f8d79c"


def episode_entry(name: str, split: str) -> dict:
    """The episode's line in the episode list: name, trigger message, now. No answers in it."""
    lines = (PROJECT_ROOT / "episodes" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
    for line in lines:
        entry = json.loads(line)
        if entry["episode"] == name:
            return entry
    raise SystemExit(f"No episode {name!r} in episodes/{split}.jsonl")


def show(event: dict) -> None:
    """Print one event of the investigation as it happens."""
    if event["event"] == "model":
        loaded = f", model loaded in {event['load_s']} s" if event["load_s"] >= 0.5 else ""
        print(f"step {event['step']}: the model read {event['prompt_tokens']} tokens and wrote "
              f"{event['output_tokens']} in {event['latency_s']} s{loaded}")
        if event["said"].strip():
            print(f"    says: {event['said'].strip()[:200]}")
        for request in event["asked_for"]:
            print(f"    asks for {request['tool']}({json.dumps(request['arguments'], ensure_ascii=False)})")
        if not event["asked_for"]:
            print("    asks for no tool: ready to report")
    elif event["event"] == "tool":
        receipt = event["call_id"] or "ERROR"
        print(f"      {receipt}: {event['result'][:150]}")
    elif event["event"] == "given":  # the one-shot baseline B3: results handed over, not asked for
        print(f"given {event['call_id']} ({event['tool']}): {event['result'][:150]}")
    elif event["event"] == "report":
        which = "report" if event["attempt"] == 1 else "corrected report (second chance)"
        print(f"{which} written in {event['latency_s']} s ({event['prompt_tokens']} tokens read, "
              f"{event['output_tokens']} written)")


def check_summary(check: Verification | None) -> dict | None:
    if check is None:
        return None
    return {"evidence_items": check.evidence_items, "failed_items": check.failed_items, "problems": check.problems}


def save_episode(system: str, name: str, split: str, run_id: str, trigger_message: str,
                 investigation: Investigation, checked: CheckedReport, seconds: float) -> dict:
    """Write one episode's trace file (start, every event, end) and return its end summary.
    Shared by the agent and the one-shot baseline B3, so the grader reads both the same way."""
    config = load_config()
    model_events = [e for e in investigation.trace if e["event"] in ("model", "report")]
    summary = {
        "event": "end", "system": system, "episode": name, "split": split, "run_id": run_id, "commit": git_commit(),
        "seconds": seconds, "model_calls": investigation.model_calls, "tool_calls": investigation.tool_calls,
        "stopped_by": investigation.stopped_by,
        "largest_prompt_tokens": max(e["prompt_tokens"] or 0 for e in model_events),
        "num_ctx": config["llm"]["num_ctx"],
        "seconds_loading_model": round(sum(e["load_s"] for e in model_events), 1),
        "outcome": checked.outcome,  # passed / fixed / verification_failed
        "first_check": check_summary(checked.first_check),
        "second_check": check_summary(checked.second_check),
        "diagnosis": checked.report.model_dump() if checked.report else None,
    }
    trace_file = PROJECT_ROOT / config["agent"]["trace_dir"] / run_id / f"{name}.jsonl"
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    start = {"event": "start", "system": system, "episode": name, "split": split, "trigger_message": trigger_message,
             "llm": config["llm"], "max_steps": config["agent"]["max_steps"] if system == "agent" else None}
    trace_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                  for e in [start, *investigation.trace, summary]), encoding="utf-8")
    summary["trace_file"] = str(trace_file.relative_to(PROJECT_ROOT))
    return summary


async def run_episode(name: str, split: str, chat: Chat, run_id: str) -> dict:
    config = load_config()
    entry = episode_entry(name, split)
    print(f"Episode {name}: {entry['trigger_message']}\n")
    started = time.perf_counter()

    server = StdioServerParameters(command=sys.executable,
                                   args=["-m", "plantagent.mcp_server", "--episode", name, "--split", split])
    async with Client(server) as client:  # starts the server program; stops it at the end of the block
        investigation = await investigate(client, chat, entry["trigger_message"], config["agent"]["max_steps"], show)
    checked = await report_with_second_chance(chat, investigation)
    seconds = round(time.perf_counter() - started, 1)
    return save_episode("agent", name, split, run_id, entry["trigger_message"], investigation, checked, seconds)


def print_check(label: str, check: dict) -> None:
    print(f"{label}: {check['failed_items']} of {check['evidence_items']} pieces of evidence failed.")
    for problem in check["problems"]:
        print(f"  - {problem}")


def print_summary(summary: dict) -> None:
    print(f"\n=== Done in {summary['seconds']} s: {summary['model_calls']} model calls, "
          f"{summary['tool_calls']} tool calls, stopped by: {summary['stopped_by']}.")
    print(f"Largest conversation the model read: {summary['largest_prompt_tokens']} tokens "
          f"(the limit, num_ctx, is {summary['num_ctx']}). Time spent loading the model: "
          f"{summary['seconds_loading_model']} s.")
    if summary["diagnosis"] is not None:
        print("\nDiagnosis:")
        print(json.dumps(summary["diagnosis"], indent=2, ensure_ascii=False))
    print()
    print_check("Fact-check of the first report", summary["first_check"])
    if summary["second_check"] is not None:
        print_check("Fact-check of the corrected report", summary["second_check"])
    print(f"Outcome: {summary['outcome']}")
    print(f"\nTrace saved to {summary['trace_file']}")


def print_table(summaries: list[dict]) -> None:
    """One line per episode: what the agent concluded (not whether it was right: no answers here)."""
    print(f"\n{'episode':<13}{'seconds':>8}{'tools':>7}  {'status':<14}{'fault':>6}  {'confidence':<11}{'outcome'}")
    for s in summaries:
        diagnosis = s["diagnosis"] or {}
        fault = diagnosis.get("fault_id")
        print(f"{s['episode']:<13}{s['seconds']:>8}{s['tool_calls']:>7}  {diagnosis.get('status', '-'):<14}"
              f"{fault if fault is not None else '-':>6}  {diagnosis.get('confidence', '-'):<11}{s['outcome']}")
    seconds = sorted(s["seconds"] for s in summaries)
    print(f"\nTime per episode: {seconds[0]} to {seconds[-1]} s (total {round(sum(seconds))} s). Largest "
          f"conversation: {max(s['largest_prompt_tokens'] for s in summaries)} tokens.")


def show_memory() -> None:
    """Where Ollama holds its models now: on the graphics card, in main memory, or split."""
    import ollama

    for model in ollama.ps().models:
        share = 100 * model.size_vram / model.size if model.size else 0
        print(f"In memory: {model.model}, {model.size / 1e9:.1f} GB, {share:.0f} % on the graphics card")


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
    parser = argparse.ArgumentParser(description="Run the agent on development episodes.")
    parser.add_argument("--episodes", nargs="+", default=[EXAMPLE_EPISODE], help="episode names from episodes/dev.jsonl")
    parser.add_argument("--trial", action="store_true", help="run the trial episodes listed in config.toml ([agent])")
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                        help="folder name for the traces (default: date and time)")
    arguments = parser.parse_args()
    config = load_config()
    names = config["agent"]["trial_episodes"] if arguments.trial else arguments.episodes
    summaries = asyncio.run(run_episodes(names, ollama_chat(config["llm"]), arguments.run_id))
    if len(summaries) > 1:
        print_table(summaries)
    show_memory()


if __name__ == "__main__":
    main()
