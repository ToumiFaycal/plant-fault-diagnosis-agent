"""Stage 1 of the monitor: put every signal on the same scale.

Each value becomes a z-score: how many "normal wobbles" (standard deviations) it is away from
its normal average. 0 = at the normal average, ±1 = a typical wobble, ±3 = really unusual.

The averages and wobbles are learned ONLY from the normal runs reserved for fitting the monitor,
and the same ones are then used for every other run.

Try it on the real data with:
    python -m plantagent.monitor.standardize
"""

import numpy as np

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import SIGNALS, load_signals


def fit_normal_stats(X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Learn each signal's normal average and normal wobble from a table of normal operation.

    X: rows = moments, columns = signals.
    Returns two rows of numbers, one value per signal (per column): (averages, wobbles).
    """
    averages = X.mean(axis=0)
    wobbles = X.std(axis=0)
    return averages, wobbles


def standardize(X: np.ndarray, averages: np.ndarray, wobbles: np.ndarray) -> np.ndarray:
    """Turn every value of X into a z-score: (value - normal average) / normal wobble.

    X: rows = moments, columns = signals. Returns a table of the same shape.
    """
    return (X - averages) / wobbles


def main() -> None:
    splits = load_config()["splits"]
    X = load_signals("train", 0, runs_between(splits["monitor_fit_runs"]))
    print(f"Normal fitting runs: {X.shape[0]:,} moments x {X.shape[1]} signals")

    averages, wobbles = fit_normal_stats(X)
    print("\nWhat the monitor learned, for four signals:")
    for tag in ("xmeas_7", "xmeas_9", "xmeas_10", "xmv_10"):
        i = SIGNALS.index(tag)
        print(f"  {tag:9} average {averages[i]:10.4f}   wobble {wobbles[i]:8.4f}")

    # The worked example: reactor temperature 120.46 °C and reactor pressure 2712 kPa.
    example = averages.copy()  # one moment where every signal sits exactly at its average...
    example[SIGNALS.index("xmeas_9")] = 120.46  # ...except these two
    example[SIGNALS.index("xmeas_7")] = 2712.0
    z = standardize(example.reshape(1, -1), averages, wobbles)[0]  # reshape: a table of one row
    print("\nThe worked example as z-scores:")
    print(f"  reactor temperature 120.46 °C -> z = {z[SIGNALS.index('xmeas_9')]:.1f}")
    print(f"  reactor pressure   2712 kPa   -> z = {z[SIGNALS.index('xmeas_7')]:.1f}")


if __name__ == "__main__":
    main()
