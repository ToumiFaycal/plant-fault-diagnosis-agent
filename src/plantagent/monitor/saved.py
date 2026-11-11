"""Save what the monitor learned to one small file, and load it back.

Why: the MCP server needs the monitor (normal averages and wobbles, the kept ways of moving, the two
alarm limits, the alarm rule), but it must never open the converted data files, which hold the
answers. So the monitor is fitted once here, only what it learned is saved, and the server loads
that file. Like saving a trained model instead of shipping its training data.

Run once (and again whenever the monitor's settings in config.toml change):
    python -m plantagent.monitor.saved
"""

from pathlib import Path
from types import SimpleNamespace

import numpy as np

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.monitor.data import load_signals
from plantagent.monitor.scores import fit_monitor, score_run


def monitor_path() -> Path:
    return PROJECT_ROOT / load_config()["data"]["monitor_file"]


def save_monitor(monitor: dict, path: Path) -> None:
    kept = monitor["kept"]
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        averages=monitor["averages"],
        wobbles=monitor["wobbles"],
        ways=monitor["patterns"].components_[:kept],  # only the kept ways of moving
        way_variances=monitor["patterns"].explained_variance_[:kept],
        t2_limit=monitor["t2_limit"],
        spe_limit=monitor["spe_limit"],
        alarm_after_consecutive=monitor["alarm_after_consecutive"],
    )


def load_monitor(path: Path) -> dict:
    """The monitor as the step 4 functions expect it (same keys as fit_monitor)."""
    with np.load(path) as saved:
        # Your score functions only read components_ and explained_variance_ from the PCA,
        # so a simple object holding those two works in its place.
        patterns = SimpleNamespace(components_=saved["ways"], explained_variance_=saved["way_variances"])
        return {
            "averages": saved["averages"],
            "wobbles": saved["wobbles"],
            "patterns": patterns,
            "kept": len(saved["way_variances"]),
            "t2_limit": float(saved["t2_limit"]),
            "spe_limit": float(saved["spe_limit"]),
            "alarm_after_consecutive": int(saved["alarm_after_consecutive"]),
        }


def main() -> None:
    monitor = fit_monitor()
    monitor["alarm_after_consecutive"] = load_config()["monitor"]["alarm_after_consecutive"]
    path = monitor_path()
    save_monitor(monitor, path)
    print(f"Saved the monitor to {path.relative_to(PROJECT_ROOT)} ({path.stat().st_size / 1000:.0f} kB): "
          f"{monitor['kept']} ways kept, T² limit {monitor['t2_limit']:.1f}, SPE limit {monitor['spe_limit']:.1f}, "
          f"alarm after {monitor['alarm_after_consecutive']} moments in a row.")

    # Check: the saved monitor scores a run exactly like the freshly fitted one.
    X = load_signals("dev", 0, {1})
    fresh, saved = score_run(monitor, X), score_run(load_monitor(path), X)
    difference = max(np.abs(fresh[0] - saved[0]).max(), np.abs(fresh[1] - saved[1]).max())
    print(f"Check on development normal run 1: largest difference in scores {difference:g}")


if __name__ == "__main__":
    main()
