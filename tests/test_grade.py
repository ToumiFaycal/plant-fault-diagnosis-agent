"""Tests for the grader: the grading key, group by group, and the counts. Made-up answers first,
then the real trial run (its traces and the development answer file are committed)."""

from plantagent.config import PROJECT_ROOT
from plantagent.evaluation.grade import (grade, grade_run, in_top_three, is_confident_error, is_correct,
                                         summarize)
from plantagent.fault_groups import fault_group


def label(fault: int, episode: str = "ep_00000001", trigger_type: str = "alarm") -> dict:
    """A made-up line of the answer file."""
    return {"episode": episode, "fault": fault, "run": 1, "group": fault_group(fault),
            "first_faulty_sample": None if fault == 0 else 161, "trigger_type": trigger_type}


def answer(status: str, fault_id: int | None = None, confidence: str = "medium", outcome: str = "passed",
           ranked: list[int] | None = None, episode: str = "ep_00000001") -> dict:
    """A made-up final summary of an investigation (the last line of a trace)."""
    diagnosis = {"status": status, "fault_id": fault_id, "confidence": confidence,
                 "ranked_candidates": ranked if ranked is not None else ([fault_id] if fault_id else [])}
    return {"event": "end", "episode": episode, "split": "dev", "outcome": outcome, "seconds": 100.0,
            "tool_calls": 7, "diagnosis": diagnosis}


# --- The grading key (is_correct is yours) ---

def test_a_normal_run_is_right_only_with_no_fault():
    assert is_correct("normal", 0, "no_fault", None)
    assert not is_correct("normal", 0, "fault", 4)
    assert not is_correct("normal", 0, "inconclusive", None)


def test_a_known_fault_needs_its_exact_number():
    assert is_correct("known", 4, "fault", 4)
    assert not is_correct("known", 4, "fault", 7)           # another fault
    assert not is_correct("known", 4, "fault", None)        # "a fault, but not one from the catalogue"
    assert not is_correct("known", 4, "inconclusive", None)
    assert not is_correct("known", 4, "no_fault", 4)        # the right number, but it says "no fault"


def test_a_hard_fault_accepts_no_fault_inconclusive_or_its_number():
    assert is_correct("hard", 3, "no_fault", None)
    assert is_correct("hard", 3, "inconclusive", None)
    assert is_correct("hard", 3, "fault", 3)
    assert not is_correct("hard", 3, "fault", 7)
    assert not is_correct("hard", 3, "fault", None)


def test_an_unknown_type_fault_needs_a_fault_without_a_number():
    assert is_correct("unknown-type", 16, "fault", None)
    assert not is_correct("unknown-type", 16, "fault", 5)   # a catalogue fault: wrong
    assert not is_correct("unknown-type", 16, "no_fault", None)
    assert not is_correct("unknown-type", 16, "inconclusive", None)


# --- Confident errors (is_confident_error is yours) ---

def test_a_confident_error_is_a_wrong_answer_given_with_high_confidence():
    assert is_confident_error(False, "fault", "high")          # wrong fault, "high": the worst case
    assert is_confident_error(False, "no_fault", "high")       # "all fine", sure of it, but wrong
    assert not is_confident_error(False, "fault", "medium")    # wrong, but not presented as sure
    assert not is_confident_error(True, "fault", "high")       # right: no error at all
    assert not is_confident_error(False, "inconclusive", "high")  # "I can't tell" never misleads


# --- The rest of the grade ---

def test_top_three_looks_at_the_answer_and_the_candidates():
    assert in_top_three(5, 1, [1, 7, 5])
    assert in_top_three(5, 5, [])
    assert not in_top_three(5, 1, [1, 7, 10])


def test_a_report_that_failed_the_fact_check_is_never_right_nor_a_confident_error():
    # The answer itself would be right, and given with high confidence: it still isn't trusted.
    graded = grade(label(4), answer("fault", 4, confidence="high", outcome="verification_failed"))
    assert (graded["correct"], graded["confident_error"], graded["top_three"]) == (False, False, False)


def test_the_summary_counts_each_group_and_trigger():
    graded = [grade(label(0, "ep_00000001", "operator"), answer("no_fault")),                  # right
              grade(label(4, "ep_00000002"), answer("fault", 7, "high", ranked=[7, 4])),        # confident error, top 3
              grade(label(3, "ep_00000003", "operator"), answer("inconclusive", confidence="low")),  # right (hard)
              grade(label(16, "ep_00000004"), answer("fault", 5, outcome="verification_failed"))]  # not trusted
    summary = summarize(graded)
    assert summary["all"] == {"episodes": 4, "right": 2, "confident_errors": 1, "not_trusted": 1}
    assert summary["groups"]["known"] == {"episodes": 1, "right": 0, "confident_errors": 1, "not_trusted": 0,
                                          "top_three": 1}
    assert summary["triggers"]["operator"]["right"] == 2


# --- The real trial run (version 2 instructions, 5 development episodes) ---

def test_the_trial_run_is_graded_as_expected():
    graded = {g["episode"]: g for g in grade_run(PROJECT_ROOT / "results" / "traces" / "2026-11-12_165741")}
    assert {name for name, g in graded.items() if g["correct"]} == {"ep_da12f9aa", "ep_da9277da"}  # normal, fault 3
    assert {name for name, g in graded.items() if g["confident_error"]} == {"ep_2a699431"}  # fault 1 → 7, high
    assert graded["ep_f6f8d79c"]["top_three"] is False  # fault 5: candidates 1, 7, 10


# --- Rule guard ---

def test_only_the_builder_and_the_graders_mention_the_answer_files():
    allowed = {"episodes/build.py", "baseline/evaluate_baseline.py", "evaluation/grade.py"}
    source = PROJECT_ROOT / "src" / "plantagent"
    mentioning = {path.relative_to(source).as_posix() for path in source.rglob("*.py")
                  if "labels_" in path.read_text(encoding="utf-8")}
    assert mentioning <= allowed, f"unexpected code mentions the answer files: {mentioning - allowed}"
