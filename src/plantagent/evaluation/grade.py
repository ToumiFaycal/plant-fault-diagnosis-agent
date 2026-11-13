"""Step 9.1: the grader. It compares what the agent concluded with the true answer.

Like a teacher with the answer key: the agent's report is the student's answer sheet, and the
answer file (episodes/labels_<split>.jsonl) is the key. Only grading code reads that file; the
agent and the plant server never do (tests check that).

What counts as right depends on the episode's group. The key was fixed in the project plan
before any result existed:

  group         true fault          right answer
  normal        0                   "no_fault"
  known         1, 2, 4-8, 10-14    "fault" with the exact fault number
  hard          3, 9, 15            "no_fault" or "inconclusive" (the plant barely changes),
                                    or "fault" with the true number
  unknown-type  16-20               "fault" with no number (none of the catalogue's faults fits)

Two more things are counted:
  - A confident error: a wrong answer given with high confidence. It's the worst kind, because
    someone would act on it. "inconclusive" says "I can't tell", so it is never one.
  - A report that failed the fact-check twice ("verification_failed") is never counted as right,
    nor as a confident error: its answer isn't trusted, and the reader is told so.

Grade one run (a folder of traces, one file per episode, written by python -m plantagent.agent):
    python -m plantagent.evaluation.grade results/traces/2026-11-12_165741
"""

import argparse
import json
from pathlib import Path

from plantagent.config import PROJECT_ROOT

GROUPS = ("normal", "known", "hard", "unknown-type")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_labels(split: str) -> dict[str, dict]:
    """The true answers of one split, by episode name."""
    return {label["episode"]: label for label in read_jsonl(PROJECT_ROOT / "episodes" / f"labels_{split}.jsonl")}


def read_answers(run_dir: Path) -> list[dict]:
    """What the agent concluded in each episode of one run: the last line ("end") of each trace file."""
    answers = []
    for trace in sorted(run_dir.glob("ep_*.jsonl")):
        end = read_jsonl(trace)[-1]
        if end.get("event") != "end" or "outcome" not in end:
            raise ValueError(f"{trace.name}: its last line isn't a final summary in the current format")
        answers.append(end)
    if not answers:
        raise ValueError(f"no trace files in {run_dir}")
    return answers


def is_correct(group: str, fault: int, status: str, fault_id: int | None) -> bool:
    """Is this answer right for this episode? One rule per group (the key at the top of this file).

    group:     "normal", "known", "hard" or "unknown-type" (from the answer file)
    fault:     the true fault number (0 = normal)
    status:    what the agent concluded: "no_fault", "fault" or "inconclusive"
    fault_id:  the fault number it named (1 to 15), or None
    """
    if group == "normal":
        return status == "no_fault"
    if group == "known":
        return status == "fault" and fault_id == fault
    if group == "hard":
        return status in ("no_fault", "inconclusive") or (status == "fault" and fault_id == fault)
    if group == "unknown-type":
        return status == "fault" and fault_id is None
    raise ValueError(f"unknown group {group!r}")


def is_confident_error(correct: bool, status: str, confidence: str) -> bool:
    """A wrong answer, given with high confidence, that commits to something ("no_fault" or "fault").

    "inconclusive" means "I can't tell", so it is never a confident error, whatever its confidence.
    """
    return not correct and confidence == "high" and status != "inconclusive"


def in_top_three(fault: int, fault_id: int | None, ranked_candidates: list[int]) -> bool:
    """Is the true fault among the agent's top candidates (or its main answer)? Used for known faults."""
    return fault == fault_id or fault in ranked_candidates


def grade(label: dict, answer: dict) -> dict:
    """One episode's grade: the truth, what the agent said, and the verdict."""
    diagnosis = answer["diagnosis"] or {}
    trusted = answer["outcome"] != "verification_failed" and answer["diagnosis"] is not None
    status, fault_id, confidence = diagnosis.get("status"), diagnosis.get("fault_id"), diagnosis.get("confidence")
    correct = trusted and is_correct(label["group"], label["fault"], status, fault_id)
    return {
        "episode": label["episode"], "fault": label["fault"], "group": label["group"],
        "trigger_type": label["trigger_type"],
        "status": status, "fault_id": fault_id, "confidence": confidence, "outcome": answer["outcome"],
        "correct": correct,
        "confident_error": trusted and is_confident_error(correct, status, confidence),
        "top_three": (trusted and in_top_three(label["fault"], fault_id, diagnosis.get("ranked_candidates", [])))
                     if label["group"] == "known" else None,
        "seconds": answer["seconds"], "tool_calls": answer["tool_calls"],
    }


def grade_run(run_dir: Path) -> list[dict]:
    """Grade every episode of one run against the answer file of its split."""
    answers = read_answers(run_dir)
    splits = {answer["split"] for answer in answers}
    if len(splits) != 1:
        raise ValueError(f"one run should cover one split, found {sorted(splits)}")
    labels = read_labels(splits.pop())
    return [grade(labels[answer["episode"]], answer) for answer in answers]


def summarize(graded: list[dict]) -> dict:
    """Counts per group and per trigger type (how the investigation started)."""
    def counts(episodes: list[dict]) -> dict:
        return {"episodes": len(episodes),
                "right": sum(e["correct"] for e in episodes),
                "confident_errors": sum(e["confident_error"] for e in episodes),
                "not_trusted": sum(e["outcome"] == "verification_failed" for e in episodes)}

    summary = {"all": counts(graded), "groups": {}, "triggers": {}}
    for group in GROUPS:
        mine = [e for e in graded if e["group"] == group]
        if mine:
            summary["groups"][group] = counts(mine)
            if group == "known":
                summary["groups"][group]["top_three"] = sum(e["top_three"] for e in mine)
    for trigger in ("alarm", "operator"):
        mine = [e for e in graded if e["trigger_type"] == trigger]
        if mine:
            summary["triggers"][trigger] = counts(mine)
    return summary


def verdict(graded: dict) -> str:
    if graded["outcome"] == "verification_failed":
        return "not trusted (failed the fact-check twice)"
    if graded["correct"]:
        return "right"
    return "WRONG, with high confidence" if graded["confident_error"] else "wrong"


def answer_text(graded: dict) -> str:
    if graded["status"] is None:
        return "(no report on the form)"
    number = f" {graded['fault_id']}" if graded["fault_id"] is not None else ""
    return f"{graded['status']}{number}, {graded['confidence']}"


def print_grades(graded: list[dict]) -> None:
    print(f"{'episode':<13}{'group':<14}{'truth':>6}  {'answer':<24}{'verdict'}")
    for g in sorted(graded, key=lambda g: (GROUPS.index(g["group"]), g["fault"], g["episode"])):
        truth = "normal" if g["fault"] == 0 else str(g["fault"])
        print(f"{g['episode']:<13}{g['group']:<14}{truth:>6}  {answer_text(g):<24}{verdict(g)}")

    summary = summarize(graded)
    print()
    for name, part in [*summary["groups"].items(), *(("started by " + t, c) for t, c in summary["triggers"].items())]:
        extra = f", true fault in the top 3: {part['top_three']}" if "top_three" in part else ""
        print(f"{name:<22} right {part['right']} of {part['episodes']}{extra}; "
              f"confident errors {part['confident_errors']}; not trusted {part['not_trusted']}")
    total = summary["all"]
    print(f"{'all':<22} right {total['right']} of {total['episodes']}; "
          f"confident errors {total['confident_errors']}; not trusted {total['not_trusted']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade one run of the agent (a folder of traces).")
    parser.add_argument("run_dir", help="for example results/traces/2026-11-12_165741")
    run_dir = Path(parser.parse_args().run_dir)
    if not run_dir.is_absolute():
        run_dir = PROJECT_ROOT / run_dir
    print_grades(grade_run(run_dir))


if __name__ == "__main__":
    main()
