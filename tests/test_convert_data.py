"""Tests for the data conversion and the settings file.

They use a tiny hand-made table instead of the real data files, so they run in
a split second and we know the right answer in advance.
"""

import pandas as pd
import pytest

from plantagent.config import load_config
from plantagent.convert_data import check_complete, runs_between, save_runs


def fake_table() -> pd.DataFrame:
    """A tiny table shaped like the real data: faults 1 and 2, runs 1 to 4, 3 samples per run.

    Like in the real files, the fault and run numbers are stored as decimals (1.0, 2.0, ...).
    """
    rows = []
    for fault in (1, 2):
        for run in (1, 2, 3, 4):
            for sample in (1, 2, 3):
                rows.append({
                    "faultNumber": float(fault),
                    "simulationRun": float(run),
                    "sample": sample,
                    "xmeas_1": fault * 100 + run + sample / 10,  # fault 2, run 3, sample 1 -> 203.1
                })
    return pd.DataFrame(rows)


# --- Examples ---

def test_runs_between_includes_both_ends():
    assert runs_between({"first": 1, "last": 5}) == {1, 2, 3, 4, 5}
    assert runs_between({"first": 7, "last": 7}) == {7}


def test_save_runs_writes_one_file_per_fault(tmp_path):
    # tmp_path is an empty folder that pytest creates for this test only.
    save_runs(fake_table(), [("dev", {1, 2})], tmp_path)

    files = sorted(path.name for path in (tmp_path / "dev").iterdir())
    assert files == ["fault_01.parquet", "fault_02.parquet"]


# --- Your turn: replace each pytest.skip(...) line with the test ---

def test_save_runs_keeps_only_the_wanted_runs(tmp_path):
    save_runs(fake_table(), [("dev", {1, 2})], tmp_path)
    table = pd.read_parquet(tmp_path / "dev" / "fault_01.parquet")
    assert set(table["simulationRun"]) == {1, 2}


def test_check_complete_stops_when_a_run_is_missing():
    table = fake_table()
    fault_1 = table[table["faultNumber"] == 1]  # the rows of fault 1: runs 1 to 4
    with pytest.raises(ValueError):
        check_complete(fault_1, {1, 5}, "fault 1")


def test_dev_and_test_runs_never_overlap():
    # This guards the "no peeking" rule: no run may be used both for developing
    # and for the final exam, even if someone edits config.toml later.
    splits = load_config()["splits"]
    runs_dev_fault = runs_between(splits["dev_fault_runs"])
    runs_test_pool = runs_between(splits["test_pool_runs"])
    assert runs_dev_fault & runs_test_pool == set()
    runs_dev_normal = runs_between(splits["dev_normal_runs"])
    assert runs_dev_normal & runs_test_pool == set()
