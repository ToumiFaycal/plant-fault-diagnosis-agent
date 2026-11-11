"""Tests for the episodes: no answer may leak to the agent, and no data from after "now"."""

import json
import re

import numpy as np
import pandas as pd
import pytest

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.episodes.build import episode_table, plan_trigger, sample_time
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


# --- Checks on the real development episodes (once they have been built) ---

EPISODE_LIST = PROJECT_ROOT / "episodes" / "dev.jsonl"
LABELS = PROJECT_ROOT / "episodes" / "labels_dev.jsonl"


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.skipif(not EPISODE_LIST.exists(), reason="the development episodes haven't been built yet")
def test_episode_list_reveals_no_answers():
    episodes = read_jsonl(EPISODE_LIST)
    for episode in episodes:
        assert set(episode) == {"episode", "trigger_message", "now_sample", "now_time"}
        assert re.fullmatch(r"ep_[0-9a-f]{8}", episode["episode"])  # a random code, nothing more
    names = [episode["episode"] for episode in episodes]
    assert len(names) == len(set(names))  # every name is different
    assert set(names) == {label["episode"] for label in read_jsonl(LABELS)}  # each episode has its answer


EPISODES_DIR = PROJECT_ROOT / load_config()["data"]["episodes_dir"]


@pytest.mark.skipif(not EPISODES_DIR.exists(), reason="no episode files on this computer (they're never on GitHub)")
def test_stored_episodes_hide_answers_and_stop_at_now():
    for episode in read_jsonl(EPISODE_LIST):
        table = pd.read_parquet(EPISODES_DIR / f"{episode['episode']}.parquet")
        assert list(table.columns) == ALLOWED_COLUMNS
        assert table["sample"].max() == episode["now_sample"]
