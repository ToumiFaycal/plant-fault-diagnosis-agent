"""Convert the downloaded .RData files into Parquet files, once.

What goes in: the four .RData files in data/raw/.
What comes out: one Parquet file per fault (fault_00 = normal) in three folders:
    data/processed/train/  training runs, for the monitor and the baseline classifier
    data/processed/dev/    testing runs we develop and debug on
    data/processed/test/   testing runs kept apart for the final exam

Only the runs listed in config.toml are kept. Run it with:
    python -m plantagent.convert_data
"""

import time

import pyreadr

from plantagent.config import PROJECT_ROOT, load_config


def runs_between(run_range: dict) -> set[int]:
    """Turn {"first": 1, "last": 5} into the set of run numbers {1, 2, 3, 4, 5}."""
    return set(range(run_range["first"], run_range["last"] + 1))


def conversion_plan(splits: dict) -> list:
    """Say which file feeds which folder, and which runs to keep.

    Each entry: (file name, name of the table inside the file, [(folder, runs to keep), ...]).
    Smallest files first, so the quick ones are saved even if the biggest one fails.
    """
    fit = runs_between(splits["monitor_fit_runs"])
    calibration = runs_between(splits["monitor_calibration_runs"])
    baseline = runs_between(splits["baseline_runs"])
    dev_normal = runs_between(splits["dev_normal_runs"])
    dev_fault = runs_between(splits["dev_fault_runs"])
    test_pool = runs_between(splits["test_pool_runs"])

    return [
        ("TEP_FaultFree_Training.RData", "fault_free_training", [("train", fit | calibration | baseline)]),
        ("TEP_FaultFree_Testing.RData", "fault_free_testing", [("dev", dev_normal), ("test", test_pool)]),
        ("TEP_Faulty_Training.RData", "faulty_training", [("train", baseline)]),
        ("TEP_Faulty_Testing.RData", "faulty_testing", [("dev", dev_fault), ("test", test_pool)]),
    ]


def check_complete(fault_table, runs: set[int], label: str) -> None:
    """Stop with a clear message if a run is missing or the runs have different lengths."""
    found = set(fault_table["simulationRun"].unique())
    if found != runs:
        raise ValueError(f"{label}: expected {len(runs)} runs, found {len(found)}")
    run_lengths = fault_table.groupby("simulationRun").size().unique()
    if len(run_lengths) != 1:
        raise ValueError(f"{label}: runs have different numbers of samples: {sorted(run_lengths)}")


def convert_file(raw_path, table_name: str, destinations: list, out_dir) -> None:
    """Read one .RData file, then save the runs we keep.

    The whole file is loaded into memory here. When this function ends, Python frees
    that memory, before the next file is read.
    """
    start = time.perf_counter()
    table = pyreadr.read_r(raw_path)[table_name]  # read_r gives back {table name: table}
    print(f"Read {raw_path.name}: {len(table):,} rows in {time.perf_counter() - start:.0f} s")
    save_runs(table, destinations, out_dir)


def save_runs(table, destinations: list, out_dir) -> None:
    """Keep only the wanted runs of a table, and save them as one Parquet file per fault."""
    for folder, runs in destinations:
        kept = table[table["simulationRun"].isin(runs)]
        # The file stores fault and run numbers as decimals (1.0): make them whole numbers.
        kept = kept.astype({"faultNumber": "int64", "simulationRun": "int64", "sample": "int64"})

        (out_dir / folder).mkdir(parents=True, exist_ok=True)
        for fault, fault_table in kept.groupby("faultNumber"):
            check_complete(fault_table, runs, f"{folder}, fault {fault}")
            fault_table = fault_table.sort_values(["simulationRun", "sample"])
            path = out_dir / folder / f"fault_{fault:02d}.parquet"
            fault_table.to_parquet(path, index=False)
            print(f"  {folder}/{path.name}: {len(runs)} runs, {len(fault_table):,} rows")


def main() -> None:
    config = load_config()
    raw_dir = PROJECT_ROOT / config["data"]["raw_dir"]
    out_dir = PROJECT_ROOT / config["data"]["processed_dir"]

    for file_name, table_name, destinations in conversion_plan(config["splits"]):
        convert_file(raw_dir / file_name, table_name, destinations, out_dir)
    print(f"Done. The Parquet files are in {out_dir}")


if __name__ == "__main__":
    main()
