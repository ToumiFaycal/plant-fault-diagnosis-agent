"""Turn recorded runs into episodes, one investigation each for the agent: the development episodes
(step 5) and the test episodes, the final exam (step 8.3).

An episode holds what a real investigator would have, and nothing more:
  - a name that says nothing about the answer (a random code like "ep_3f9a1c2e");
  - a trigger message saying why someone is asking ("The plant monitor raised an alarm at 09:12...");
  - the plant's recorded signals up to "now" only: nothing from the future.
The answers (which fault, which run) go into a separate labels file that only the grader reads.

When does the investigation start ("now")?
  - If the monitor alarms during the run: 1 hour after its first alarm.
  - If it never alarms: an operator reports, at a random time 1 to 6 hours after 8:00, that the plant
    looks off, and "now" is 1 hour after that report. Normal and faulty runs get the same treatment,
    so the time of the report doesn't give the answer away.

Writes:
  data/episodes/<name>.parquet   the signals each episode may see (inside data/: never committed)
  episodes/<split>.jsonl         one line per episode: name, trigger message, now (committed)
  episodes/labels_<split>.jsonl  the answers, for the grader only (committed)

Once committed, a list is frozen: building again must give exactly the same list. If it does, only
the signal files are written again (they're not on GitHub, so a fresh copy of the project needs them).
If it doesn't, nothing is written.

Run it with:
    python -m plantagent.episodes.build               (the development episodes)
    python -m plantagent.episodes.build --split test  (the test episodes: it only says how many)
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.convert_data import runs_between
from plantagent.fault_groups import fault_group
from plantagent.monitor.alarms import alarm_run
from plantagent.monitor.data import SIGNALS, load_signals_by_run
from plantagent.monitor.scores import fit_monitor

MINUTES_PER_SAMPLE = 3
SPLITS = ("dev", "test")
LIST_DIR = PROJECT_ROOT / "episodes"


class FrozenListError(Exception):
    """Building again gave a different episode list than the one already saved."""


def sample_time(sample: int) -> str:
    """The clock time of a sample, counted from the start of the run: sample 1 is "00:03", 160 is "08:00"."""
    hours, minutes = divmod(sample * MINUTES_PER_SAMPLE, 60)
    return f"{hours:02d}:{minutes:02d}"


def episode_table(X: np.ndarray, now_sample: int) -> pd.DataFrame:
    """What an episode is allowed to see: the sample number, its clock time and the 52 signals,
    from the first sample up to and including `now_sample`. Nothing about the answer."""
    seen = X[:now_sample]
    table = pd.DataFrame(seen, columns=SIGNALS)
    samples = np.arange(1, len(seen) + 1)
    table.insert(0, "sample_time", [sample_time(s) for s in samples])
    table.insert(0, "sample", samples)
    return table


def plan_trigger(first_alarm: int | None, report_sample: int, run_length: int, settings: dict) -> dict:
    """Decide how the episode starts: from the first alarm if there is one, otherwise from an operator's report.

    first_alarm: the first sample in alarm (None if the monitor never alarms).
    report_sample: when an operator would report, used only if there is no alarm.
    """
    wait = settings["investigate_after_minutes"] // MINUTES_PER_SAMPLE
    if first_alarm is not None:
        now = min(first_alarm + wait, run_length)
        message = f"The plant monitor raised an alarm at {sample_time(first_alarm)}. It is now {sample_time(now)}."
        return {"trigger_type": "alarm", "event_sample": first_alarm, "now_sample": now, "message": message}
    now = min(report_sample + wait, run_length)
    message = f"An operator says the plant looks off around {sample_time(report_sample)}. It is now {sample_time(now)}."
    return {"trigger_type": "operator", "event_sample": report_sample, "now_sample": now, "message": message}


def check_not_changed(path: Path, new_text: str) -> None:
    """A saved episode list is frozen: it may be written once, and never changed after that.

    If `path` already exists and holds a different text than `new_text`, raise FrozenListError.
    If it doesn't exist yet, or holds exactly `new_text`, do nothing (writing it is fine).
    """
    if path.exists() and path.read_text(encoding="utf-8") != new_text:
        raise FrozenListError(f"{path.name} already exists and is different: nothing was written.")


def read_names(path: Path) -> set[str]:
    """The episode names in a saved list."""
    return {json.loads(line)["episode"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def build_episodes(split: str) -> dict:
    """Build every episode of one split ("dev" or "test"). Returns how many, how they start, and
    whether the list was already saved (and is unchanged)."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}, not {split!r}")
    config = load_config()
    splits, settings = config["splits"], config["episodes"]
    in_a_row = config["monitor"]["alarm_after_consecutive"]
    first_faulty = config["data"]["first_faulty_sample_testing"]
    random = np.random.default_rng(settings["seed"] if split == "dev" else settings["test_seed"])
    monitor = fit_monitor()

    report_window = settings["operator_report_after_hours"]
    episodes, labels, tables, used_names = [], [], {}, set()

    for fault in range(0, 21):
        runs = runs_between(splits[f"{split}_normal_runs"] if fault == 0 else splits[f"{split}_fault_runs"])
        for run, X in load_signals_by_run(split, fault, runs).items():
            # Draw a name and a report time for every run, alarm or not, so the draws never shift.
            name = f"ep_{random.integers(0, 2**32):08x}"
            while name in used_names:
                name = f"ep_{random.integers(0, 2**32):08x}"
            used_names.add(name)
            report_minutes = random.integers(report_window["first"] * 60, report_window["last"] * 60 + 1)
            report_sample = first_faulty - 1 + int(report_minutes) // MINUTES_PER_SAMPLE

            alarm = np.flatnonzero(alarm_run(monitor, X, in_a_row))
            first_alarm = int(alarm[0]) + 1 if len(alarm) else None
            trigger = plan_trigger(first_alarm, report_sample, len(X), settings)

            tables[name] = episode_table(X, trigger["now_sample"])
            episodes.append({"episode": name, "trigger_message": trigger["message"],
                             "now_sample": trigger["now_sample"], "now_time": sample_time(trigger["now_sample"])})
            labels.append({"episode": name, "fault": fault, "run": run, "group": fault_group(fault),
                           "first_faulty_sample": None if fault == 0 else first_faulty,
                           "trigger_type": trigger["trigger_type"]})

    # Every episode name is used once in the whole project, so a name never points to two episodes.
    for other in SPLITS:
        other_list = LIST_DIR / f"{other}.jsonl"
        if other != split and other_list.exists() and used_names & read_names(other_list):
            raise ValueError(f"an episode name is already used in {other_list.name}: change the seed")

    order = random.permutation(len(episodes))  # shuffle, so the position in the list says nothing either
    texts = {f"{split}.jsonl": [episodes[i] for i in order], f"labels_{split}.jsonl": [labels[i] for i in order]}
    texts = {file_name: "\n".join(json.dumps(record) for record in records) + "\n"
             for file_name, records in texts.items()}
    already_saved = (LIST_DIR / f"{split}.jsonl").exists()
    for file_name, text in texts.items():  # check both lists before writing anything
        check_not_changed(LIST_DIR / file_name, text)

    LIST_DIR.mkdir(exist_ok=True)
    for file_name, text in texts.items():
        (LIST_DIR / file_name).write_text(text, encoding="utf-8")
    episodes_dir = PROJECT_ROOT / config["data"]["episodes_dir"]
    episodes_dir.mkdir(parents=True, exist_ok=True)
    for name, table in tables.items():
        table.to_parquet(episodes_dir / f"{name}.parquet", index=False)

    alarms = sum(label["trigger_type"] == "alarm" for label in labels)
    return {"episodes": len(episodes), "alarm": alarms, "operator": len(episodes) - alarms,
            "already_saved": already_saved}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the episodes of one split.")
    parser.add_argument("--split", choices=SPLITS, default="dev")
    split = parser.parse_args().split
    built = build_episodes(split)

    if built["already_saved"]:
        print(f"The {split} list was already saved, and building again gave exactly the same list.")
    if split == "dev":
        print(f"{built['episodes']} development episodes: {built['alarm']} start from an alarm, "
              f"{built['operator']} from an operator's report.")
    else:
        # Nothing else about the test episodes is shown: nobody looks at the final exam before it's taken.
        print(f"{built['episodes']} test episodes.")
    print(f"Signals in {PROJECT_ROOT / load_config()['data']['episodes_dir']}; "
          f"list in episodes/{split}.jsonl; answers in episodes/labels_{split}.jsonl.")
    if split == "test" and not built["already_saved"]:
        print("Commit episodes/test.jsonl and episodes/labels_test.jsonl now: from then on the list is frozen.")


if __name__ == "__main__":
    main()
