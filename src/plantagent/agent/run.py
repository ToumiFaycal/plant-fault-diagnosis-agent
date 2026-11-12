"""Run the agent on one development episode, from start to finish, and show every step.

    python -m plantagent.agent                          (the example episode ep_f6f8d79c)
    python -m plantagent.agent --episode ep_3f9a1c2e    (any episode from episodes/dev.jsonl)

What happens: the plant-historian server is started for the episode (a separate program, over
stdio), Qwen3 investigates through its tools, writes its report on the Diagnosis form, and the
fact-checker checks every piece of evidence. Everything is saved to
results/traces/<run_id>/<episode>.jsonl. Needs Ollama running, and the saved monitor and search
index (python -m plantagent.monitor.saved, python -m plantagent.docsearch).
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

from mcp import Client, StdioServerParameters

from plantagent.agent.loop import Chat, investigate, ollama_chat, write_report
from plantagent.agent.verifier import verify
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
    elif event["event"] == "report":
        print(f"report written in {event['latency_s']} s ({event['prompt_tokens']} tokens read, "
              f"{event['output_tokens']} written)")


async def run_episode(name: str, split: str, chat: Chat, run_id: str) -> dict:
    config = load_config()
    entry = episode_entry(name, split)
    print(f"Episode {name}: {entry['trigger_message']}\n")
    started = time.perf_counter()

    server = StdioServerParameters(command=sys.executable,
                                   args=["-m", "plantagent.mcp_server", "--episode", name, "--split", split])
    async with Client(server) as client:  # starts the server program; stops it at the end of the block
        investigation = await investigate(client, chat, entry["trigger_message"], config["agent"]["max_steps"], show)
    report = await write_report(chat, investigation)
    verification = verify(report, investigation.calls) if report else None
    seconds = round(time.perf_counter() - started, 1)

    model_events = [e for e in investigation.trace if e["event"] in ("model", "report")]
    summary = {
        "event": "end", "episode": name, "split": split, "run_id": run_id, "commit": git_commit(),
        "seconds": seconds, "model_calls": investigation.model_calls, "tool_calls": investigation.tool_calls,
        "stopped_by": investigation.stopped_by,
        "largest_prompt_tokens": max(e["prompt_tokens"] or 0 for e in model_events),
        "num_ctx": config["llm"]["num_ctx"],
        "seconds_loading_model": round(sum(e["load_s"] for e in model_events), 1),
        "report_fits_form": report is not None,
        "evidence_items": verification.evidence_items if verification else None,
        "evidence_failed": verification.failed_items if verification else None,
        "problems": verification.problems if verification else None,
        "diagnosis": report.model_dump() if report else None,
    }
    trace_file = PROJECT_ROOT / config["agent"]["trace_dir"] / run_id / f"{name}.jsonl"
    trace_file.parent.mkdir(parents=True, exist_ok=True)
    start = {"event": "start", "episode": name, "split": split, "trigger_message": entry["trigger_message"],
             "llm": config["llm"], "max_steps": config["agent"]["max_steps"]}
    trace_file.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n"
                                  for e in [start, *investigation.trace, summary]), encoding="utf-8")
    summary["trace_file"] = str(trace_file.relative_to(PROJECT_ROOT))
    return summary


def print_summary(summary: dict) -> None:
    print(f"\n=== Done in {summary['seconds']} s: {summary['model_calls']} model calls, "
          f"{summary['tool_calls']} tool calls, stopped by: {summary['stopped_by']}.")
    print(f"Largest conversation the model read: {summary['largest_prompt_tokens']} tokens "
          f"(the limit, num_ctx, is {summary['num_ctx']}). Time spent loading the model: "
          f"{summary['seconds_loading_model']} s.")
    if summary["diagnosis"] is None:
        print("The report did not fit the Diagnosis form (see the trace).")
    else:
        print("\nDiagnosis:")
        print(json.dumps(summary["diagnosis"], indent=2, ensure_ascii=False))
        print(f"\nFact-check: {summary['evidence_failed']} of {summary['evidence_items']} pieces of evidence failed.")
        for problem in summary["problems"]:
            print(f"  - {problem}")
    print(f"\nTrace saved to {summary['trace_file']}")


def show_memory() -> None:
    """Where Ollama holds its models now: on the graphics card, in main memory, or split."""
    import ollama

    for model in ollama.ps().models:
        share = 100 * model.size_vram / model.size if model.size else 0
        print(f"In memory: {model.model}, {model.size / 1e9:.1f} GB, {share:.0f} % on the graphics card")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent on one development episode.")
    parser.add_argument("--episode", default=EXAMPLE_EPISODE)
    parser.add_argument("--run-id", default=datetime.now().strftime("%Y-%m-%d_%H%M%S"),
                        help="folder name for the trace (default: date and time)")
    arguments = parser.parse_args()
    summary = asyncio.run(run_episode(arguments.episode, "dev", ollama_chat(load_config()["llm"]), arguments.run_id))
    print_summary(summary)
    show_memory()


if __name__ == "__main__":
    main()
