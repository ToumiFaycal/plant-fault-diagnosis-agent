"""Tests for the episodes: no answer may leak to the agent, and no data from after "now"."""

import json
import re

import numpy as np
import pandas as pd
import pytest

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.convert_data import runs_between
from plantagent.episodes.build import FrozenListError, check_not_changed, episode_table, plan_trigger, sample_time
from plantagent.monitor.data import SIGNALS

ALLOWED_COLUMNS = ["sample", "sample_time"] + SIGNALS
SETTINGS = {"investigate_after_minutes": 60}


def fake_run(length: int = 10) -> np.ndarray:
    """A made-up run: `length` moments x 52 signals, each value equal to its sample number."""
    return np.repeat(np.arange(1, length + 1, dtype=float).reshape(-1, 1), len(SIGNALS), axis=1)


def test_sample_times_are_counted_from_the_start_of_the_run():
    assert sample_time(1) == "00:03"
    assert sample_time(160) == "08:00"
    assert sample_time(960) == "48:00"


def test_now_is_one_hour_after_the_first_alarm():
    trigger = plan_trigger(first_alarm=164, report_sample=200, run_length=960, settings=SETTINGS)
    assert trigger["trigger_type"] == "alarm"
    assert trigger["now_sample"] == 184  # 164 + 20 samples of 3 minutes
    assert "08:12" in trigger["message"] and "09:12" in trigger["message"]


def test_without_an_alarm_an_operator_reports():
    trigger = plan_trigger(first_alarm=None, report_sample=200, run_length=960, settings=SETTINGS)
    assert trigger["trigger_type"] == "operator"
    assert trigger["now_sample"] == 220


def test_episode_table_has_no_answer_columns():
    episode = episode_table(fake_run(), 5)
    assert list(episode.columns) == ALLOWED_COLUMNS
    assert "faultNumber" not in episode.columns
    assert "simulationRun" not in episode.columns


def test_episode_table_stops_at_now():
    episode = episode_table(fake_run(), 5)
    assert len(episode) == 5
    assert episode["sample"].max() == 5
    assert episode["xmeas_1"].max() == 5


# --- A saved list is frozen (check_not_changed is yours) ---

def test_a_new_list_or_the_same_list_again_is_fine(tmp_path):
    path = tmp_path / "test.jsonl"
    check_not_changed(path, '{"episode": "ep_00000001"}\n')  # not saved yet: fine
    path.write_text('{"episode": "ep_00000001"}\n', encoding="utf-8")
    check_not_changed(path, '{"episode": "ep_00000001"}\n')  # exactly the same: fine


def test_a_saved_list_cannot_change(tmp_path):
    path = tmp_path / "test.jsonl"
    path.write_text('{"episode": "ep_00000001"}\n', encoding="utf-8")
    with pytest.raises(FrozenListError, match="test.jsonl"):
        check_not_changed(path, '{"episode": "ep_00000002"}\n')
    assert path.read_text(encoding="utf-8") == '{"episode": "ep_00000001"}\n'  # untouched


def test_checking_a_list_never_writes_it(tmp_path):
    # Checking and writing are two separate jobs. The builder checks BOTH lists first and writes
    # only when both are fine; if checking also wrote, a failed check on the second list would
    # leave the first one already written, while the error says "nothing was written".
    path = tmp_path / "test.jsonl"
    check_not_changed(path, '{"episode": "ep_00000001"}\n')
    assert not path.exists()


def test_test_runs_come_from_the_pool_and_never_from_development():
    splits = load_config()["splits"]
    pool = runs_between(splits["test_pool_runs"])
    test_runs = runs_between(splits["test_normal_runs"]) | runs_between(splits["test_fault_runs"])
    dev_runs = runs_between(splits["dev_normal_runs"]) | runs_between(splits["dev_fault_runs"])
    assert test_runs <= pool  # only runs that were kept apart for the final exam
    assert test_runs & dev_runs == set()


# --- Checks on the real episodes (once they have been built) ---

LIST_DIR = PROJECT_ROOT / "episodes"
EPISODES_DIR = PROJECT_ROOT / load_config()["data"]["episodes_dir"]


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def saved_list(split: str) -> list[dict]:
    path = LIST_DIR / f"{split}.jsonl"
    if not path.exists():
        pytest.skip(f"the {split} episodes haven't been built yet")
    return read_jsonl(path)


@pytest.mark.parametrize("split", ["dev", "test"])
def test_episode_list_reveals_no_answers(split):
    episodes = saved_list(split)
    for episode in episodes:
        assert set(episode) == {"episode", "trigger_message", "now_sample", "now_time"}
        assert re.fullmatch(r"ep_[0-9a-f]{8}", episode["episode"])  # a random code, nothing more
    names = [episode["episode"] for episode in episodes]
    assert len(names) == len(set(names))  # every name is different
    labels = read_jsonl(LIST_DIR / f"labels_{split}.jsonl")
    assert set(names) == {label["episode"] for label in labels}  # each episode has its answer


def test_development_and_test_episodes_never_share_a_name():
    dev, test = saved_list("dev"), saved_list("test")
    assert {e["episode"] for e in dev} & {e["episode"] for e in test} == set()


@pytest.mark.skipif(not EPISODES_DIR.exists(), reason="no episode files on this computer (they're never on GitHub)")
@pytest.mark.parametrize("split", ["dev", "test"])
def test_stored_episodes_hide_answers_and_stop_at_now(split):
    for episode in saved_list(split):
        table = pd.read_parquet(EPISODES_DIR / f"{episode['episode']}.parquet")
        assert list(table.columns) == ALLOWED_COLUMNS
        assert table["sample"].max() == episode["now_sample"]
