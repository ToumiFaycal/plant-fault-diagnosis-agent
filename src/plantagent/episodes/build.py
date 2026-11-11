"""Step 5: turn each development run into an episode, one investigation for the agent.

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
  episodes/dev.jsonl             one line per episode: name, trigger message, now (committed)
  episodes/labels_dev.jsonl      the answers, for the grader only (committed)

Run it with:
    python -m plantagent.episodes.build
"""

import json

import numpy as np
import pandas as pd

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.convert_data import runs_between
from plantagent.fault_groups import fault_group
from plantagent.monitor.alarms import alarm_run
from plantagent.monitor.data import SIGNALS, load_signals_by_run
from plantagent.monitor.scores import fit_monitor

MINUTES_PER_SAMPLE = 3


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


def build_dev_episodes() -> None:
    config = load_config()
    splits, settings = config["splits"], config["episodes"]
    in_a_row = config["monitor"]["alarm_after_consecutive"]
    first_faulty = config["data"]["first_faulty_sample_testing"]
    random = np.random.default_rng(settings["seed"])
    monitor = fit_monitor()

    episodes_dir = PROJECT_ROOT / config["data"]["episodes_dir"]
    episodes_dir.mkdir(parents=True, exist_ok=True)
    report_window = settings["operator_report_after_hours"]
    episodes, labels, used_names = [], [], set()

    for fault in range(0, 21):
        runs = runs_between(splits["dev_normal_runs"] if fault == 0 else splits["dev_fault_runs"])
        for run, X in load_signals_by_run("dev", fault, runs).items():
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

            episode_table(X, trigger["now_sample"]).to_parquet(episodes_dir / f"{name}.parquet", index=False)
            episodes.append({"episode": name, "trigger_message": trigger["message"],
                             "now_sample": trigger["now_sample"], "now_time": sample_time(trigger["now_sample"])})
            labels.append({"episode": name, "fault": fault, "run": run, "group": fault_group(fault),
                           "first_faulty_sample": None if fault == 0 else first_faulty,
                           "trigger_type": trigger["trigger_type"]})

    order = random.permutation(len(episodes))  # shuffle, so the position in the list says nothing either
    out_dir = PROJECT_ROOT / "episodes"
    out_dir.mkdir(exist_ok=True)
    for file_name, records in (("dev.jsonl", episodes), ("labels_dev.jsonl", labels)):
        lines = [json.dumps(records[i]) for i in order]
        (out_dir / file_name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    alarms = sum(label["trigger_type"] == "alarm" for label in labels)
    print(f"Built {len(episodes)} development episodes: {alarms} start from an alarm, "
          f"{len(episodes) - alarms} from an operator's report.")
    print(f"Signals in {episodes_dir}; list in episodes/dev.jsonl; answers in episodes/labels_dev.jsonl.")


if __name__ == "__main__":
    build_dev_episodes()
