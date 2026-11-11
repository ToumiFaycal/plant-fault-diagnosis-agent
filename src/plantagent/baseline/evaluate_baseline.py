"""How well baseline B2 (the classifier) names faults on the development episodes.

1. Train the classifier on the labelled training runs (about 2 minutes).
2. For each development episode, look only at what the episode shows: its last hour, up to "now".
3. Compare its answer with the true one (from episodes/labels_dev.jsonl), group by group:
   - normal runs: right if it says "no fault" (class 0);
   - known faults: right if its top answer is the exact fault; also counted: the fault is in its top 3;
   - hard faults (3, 9, 15): acceptable if it says "no fault" or the right fault;
   - unknown-type faults (16-20): right if it says "a fault of an unknown type", i.e. any of 16-20.
This is a simple first grading. The full grader (step 9) will grade B2 and the agent the same way.

The table is printed, saved to results/baseline_dev.json, and added to the log results/RESULTS.md.

Run it once with:
    python -m plantagent.baseline.evaluate_baseline
"""

import json
import time
from datetime import date

import numpy as np
import pandas as pd

from plantagent.baseline.classifier import episode_features, train_classifier, training_set
from plantagent.config import PROJECT_ROOT, load_config
from plantagent.fault_groups import fault_group
from plantagent.results_log import git_commit, save_results

GROUPS = ("normal", "known", "hard", "unknown-type")


def read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_right(fault: int, answer: int) -> bool:
    """Is the classifier's top answer right (or acceptable) for an episode of this fault?"""
    group = fault_group(fault)
    if group == "normal":
        return answer == 0
    if group == "hard":
        return answer in (0, fault)
    if group == "unknown-type":
        return answer >= 16
    return answer == fault


def main() -> None:
    config = load_config()
    started = time.time()
    features, answers = training_set()
    print(f"Training on {len(answers):,} one-hour windows from the training runs...")
    model = train_classifier(features, answers)
    training_seconds = round(time.time() - started)

    episodes_dir = PROJECT_ROOT / config["data"]["episodes_dir"]
    episodes = read_jsonl(PROJECT_ROOT / "episodes" / "dev.jsonl")
    labels = {label["episode"]: label for label in read_jsonl(PROJECT_ROOT / "episodes" / "labels_dev.jsonl")}
    seen = np.array([episode_features(pd.read_parquet(episodes_dir / f"{e['episode']}.parquet")) for e in episodes])
    probabilities = model.predict_proba(seen)

    predictions = []
    for episode, chances in zip(episodes, probabilities):
        best = np.argsort(chances)[::-1][:3]
        fault = labels[episode["episode"]]["fault"]
        predictions.append({
            "episode": episode["episode"],
            "fault": fault,
            "group": fault_group(fault),
            "top3": [int(model.classes_[j]) for j in best],
            "top3_probability": [round(float(chances[j]), 2) for j in best],
        })

    results = {
        "date": date.today().isoformat(),
        "commit": git_commit(),
        "settings": config["baseline"],
        "training_windows": len(answers),
        "training_seconds": training_seconds,
        "groups": {},
        "faults": {},
        "episodes": predictions,
    }
    for group in GROUPS:
        mine = [p for p in predictions if p["group"] == group]
        results["groups"][group] = {
            "episodes": len(mine),
            "right": sum(is_right(p["fault"], p["top3"][0]) for p in mine),
            "true_fault_in_top3": sum(p["fault"] in p["top3"] for p in mine),
            "median_probability": float(np.median([p["top3_probability"][0] for p in mine])),
        }
    for fault in range(0, 21):
        mine = [p for p in predictions if p["fault"] == fault]
        results["faults"][fault] = {
            "group": fault_group(fault),
            "episodes": len(mine),
            "right": sum(is_right(fault, p["top3"][0]) for p in mine),
            "answers": sorted(p["top3"][0] for p in mine),
            "median_probability": float(np.median([p["top3_probability"][0] for p in mine])),
        }

    report = make_report(results)
    print(report)
    save_results("baseline_dev.json", results, report)


def make_report(results: dict) -> str:
    groups = results["groups"]
    settings = results["settings"]
    lines = [
        f"## {results['date']}, development episodes: the classifier (baseline B2)",
        "",
        f"Commit `{results['commit']}`. Random forest of {settings['trees']} trees, trained on "
        f"{results['training_windows']:,} one-hour windows of training runs 1–50 (normal and every fault, "
        f"faults only after their start), in {results['training_seconds']} s. Each episode is judged on its last hour.",
        "",
        f"- Normal runs, said \"no fault\": {groups['normal']['right']} of {groups['normal']['episodes']} "
        f"(median probability of its answer {groups['normal']['median_probability']:.2f}).",
        f"- Known faults, named exactly: {groups['known']['right']} of {groups['known']['episodes']}; "
        f"true fault in its top 3: {groups['known']['true_fault_in_top3']} of {groups['known']['episodes']} "
        f"(median probability {groups['known']['median_probability']:.2f}).",
        f"- Hard faults, acceptable (\"no fault\" or the right fault): {groups['hard']['right']} of "
        f"{groups['hard']['episodes']} (median probability {groups['hard']['median_probability']:.2f}).",
        f"- Unknown-type faults, said \"a fault of an unknown type\" (16–20): {groups['unknown-type']['right']} of "
        f"{groups['unknown-type']['episodes']} (median probability {groups['unknown-type']['median_probability']:.2f}).",
        "",
        "| Fault | Group | Right | Its answers (0 = no fault) | Median probability |",
        "|---|---|---|---|---|",
    ]
    for fault, result in results["faults"].items():
        answers = ", ".join(str(a) for a in result["answers"])
        lines.append(f"| {fault} | {result['group']} | {result['right']} of {result['episodes']} | {answers} | "
                     f"{result['median_probability']:.2f} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
