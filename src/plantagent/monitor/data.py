"""Load the plant's signals as plain tables of numbers, the form the monitor's maths works on.

Each table has one row per moment (one sample every 3 minutes) and one column per signal,
always in the same order: the 52 signals listed in knowledge/tags.csv.
"""

import numpy as np
import pandas as pd

from plantagent.config import PROJECT_ROOT, load_config

# The 52 signal names, in the order of knowledge/tags.csv (a test checks it matches the data).
SIGNALS = list(pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")["tag"])


def load_signals(folder: str, fault: int, runs: set[int]) -> np.ndarray:
    """Return the signals of the given runs of one converted file, as a table of numbers.

    folder: "train", "dev" or "test" (inside data/processed/)
    fault:  0 for normal operation, 1 to 20 for a fault
    runs:   the run numbers to keep, for example runs_between(splits["monitor_fit_runs"])
    """
    processed_dir = PROJECT_ROOT / load_config()["data"]["processed_dir"]
    table = pd.read_parquet(processed_dir / folder / f"fault_{fault:02d}.parquet")
    table = table[table["simulationRun"].isin(runs)]
    return table[SIGNALS].to_numpy()  # drop the names: rows = moments, columns = signals


def load_signals_by_run(folder: str, fault: int, runs: set[int]) -> dict[int, np.ndarray]:
    """Like load_signals, but keeps the runs apart: {run number: table of that run's signals}.

    Needed when something must not run across the end of one run into the next one,
    like counting moments in a row.
    """
    processed_dir = PROJECT_ROOT / load_config()["data"]["processed_dir"]
    table = pd.read_parquet(processed_dir / folder / f"fault_{fault:02d}.parquet")
    table = table[table["simulationRun"].isin(runs)]
    return {int(run): part[SIGNALS].to_numpy() for run, part in table.groupby("simulationRun")}
