"""Stage 6 of the monitor: how well it works on its own, on the development runs (baseline B1).

- False alarms: how often it alarms on healthy runs (calibration runs and normal development runs).
- Detection: for each fault, in how many of its 5 development runs it alarms after the fault starts,
  and how long after the start (the delay). Also whether any fault run alarms before its fault starts.

The table is printed, saved to results/monitor_dev.json, and added to the log results/RESULTS.md.

Run it once with:
    python -m plantagent.monitor.evaluate_monitor
"""

from datetime import date

import numpy as np

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.fault_groups import fault_group
from plantagent.monitor.alarms import alarm_run
from plantagent.monitor.data import load_signals_by_run
from plantagent.monitor.scores import fit_monitor
from plantagent.results_log import git_commit, save_results


def false_alarms(monitor: dict, runs: dict, in_a_row: int) -> dict:
    """On healthy runs: share of moments in alarm, runs that alarm at least once, and how many
    separate alarms happen in how many hours."""
    alarms = [alarm_run(monitor, X, in_a_row) for X in runs.values()]
    # An alarm "begins" at a moment in alarm whose previous moment wasn't (or at the very first moment).
    separate = sum(int(a[0]) + int(np.sum(a[1:] & ~a[:-1])) for a in alarms)
    return {
        "moments_in_alarm_percent": round(float(np.mean(np.concatenate(alarms))) * 100, 2),
        "runs_with_an_alarm": int(sum(a.any() for a in alarms)),
        "runs": len(alarms),
        "separate_alarms": separate,
        "hours": sum(len(a) for a in alarms) * 3 / 60,
    }


def how_often(result: dict) -> str:
    """'11 separate false alarms in 1250 hours (one every 114 hours)', in words."""
    if result["separate_alarms"] == 0:
        return f"no false alarm in {result['hours']:.0f} hours"
    every = result["hours"] / result["separate_alarms"]
    return f"{result['separate_alarms']} separate false alarms in {result['hours']:.0f} hours (one every {every:.0f} hours)"


def detection(monitor: dict, runs: dict, in_a_row: int, first_faulty_sample: int) -> dict:
    """For the runs of one fault: alarms before the start, runs detected after it, delays in minutes."""
    start = first_faulty_sample - 1  # position of the first faulty sample (positions count from 0)
    before, delays = 0, []
    for X in runs.values():
        alarm = alarm_run(monitor, X, in_a_row)
        before += bool(alarm[:start].any())
        after = np.flatnonzero(alarm[start:])  # positions of alarms from the fault start on
        if len(after):
            delays.append(int(after[0] + 1) * 3)  # the first faulty sample is 3 minutes after the start
    return {
        "runs": len(runs),
        "runs_alarming_before_fault": before,
        "runs_detected": len(delays),
        "median_delay_min": float(np.median(delays)) if delays else None,
    }


def main() -> None:
    config = load_config()
    splits = config["splits"]
    in_a_row = config["monitor"]["alarm_after_consecutive"]
    first_faulty_sample = config["data"]["first_faulty_sample_testing"]
    monitor = fit_monitor()

    results = {
        "date": date.today().isoformat(),
        "commit": git_commit(),
        "alarm_after_consecutive": in_a_row,
        "ways_kept": monitor["kept"],
        "t2_limit": round(float(monitor["t2_limit"]), 1),
        "spe_limit": round(float(monitor["spe_limit"]), 1),
        "calibration": false_alarms(monitor, load_signals_by_run("train", 0, runs_between(splits["monitor_calibration_runs"])), in_a_row),
        "normal_dev": false_alarms(monitor, load_signals_by_run("dev", 0, runs_between(splits["dev_normal_runs"])), in_a_row),
        "faults": {},
    }
    for fault in range(1, 21):
        runs = load_signals_by_run("dev", fault, runs_between(splits["dev_fault_runs"]))
        results["faults"][fault] = {"group": fault_group(fault), **detection(monitor, runs, in_a_row, first_faulty_sample)}

    report = make_report(results)
    print(report)
    save_results("monitor_dev.json", results, report)


def make_report(results: dict) -> str:
    calibration, normal = results["calibration"], results["normal_dev"]
    faults = results["faults"]
    detected = {group: [0, 0] for group in ("known", "hard", "unknown-type")}
    for result in faults.values():
        detected[result["group"]][0] += result["runs_detected"]
        detected[result["group"]][1] += result["runs"]
    lines = [
        f"## {results['date']}, development runs: the monitor alone (baseline B1)",
        "",
        f"Commit `{results['commit']}`. Alarm after {results['alarm_after_consecutive']} moments in a row above a limit; "
        f"{results['ways_kept']} ways kept; limits T² {results['t2_limit']}, SPE {results['spe_limit']}.",
        "",
        f"- Healthy calibration runs: {calibration['moments_in_alarm_percent']} % of moments in alarm; "
        f"{calibration['runs_with_an_alarm']} of {calibration['runs']} runs alarm at least once; {how_often(calibration)}.",
        f"- Normal development runs: {normal['moments_in_alarm_percent']} % of moments in alarm; "
        f"{normal['runs_with_an_alarm']} of {normal['runs']} runs alarm at least once; {how_often(normal)}.",
        f"- Fault runs alarming before their fault starts: "
        f"{sum(r['runs_alarming_before_fault'] for r in faults.values())} of {sum(r['runs'] for r in faults.values())}.",
        "- Fault runs detected: " + "; ".join(f"{group} {n} of {total}" for group, (n, total) in detected.items()) + ".",
        "",
        "| Fault | Group | Runs detected | Median delay (min) |",
        "|---|---|---|---|",
    ]
    for fault, result in faults.items():
        delay = "–" if result["median_delay_min"] is None else f"{result['median_delay_min']:g}"
        lines.append(f"| {fault} | {result['group']} | {result['runs_detected']} of {result['runs']} | {delay} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
