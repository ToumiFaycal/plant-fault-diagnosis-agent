"""Tests for baseline B2 (the classifier): what it looks at, and which examples it learns from."""

import numpy as np

from plantagent.baseline.classifier import episode_features, window_ends, window_features
from plantagent.episodes.build import episode_table
from plantagent.monitor.data import SIGNALS


def rising_run(length: int) -> np.ndarray:
    """A made-up run: every signal equals the sample number (1, 2, 3, ...), so it rises by 1 every 3 minutes."""
    return np.repeat(np.arange(1, length + 1, dtype=float).reshape(-1, 1), len(SIGNALS), axis=1)


def test_features_of_a_steady_rise():
    features = window_features(rising_run(20))  # one hour: values 1 to 20
    signals = len(SIGNALS)
    assert features.shape == (3 * signals,)  # average, wobble and slope of each of the 52 signals
    assert np.allclose(features[:signals], 10.5)  # the average of 1..20
    assert np.allclose(features[signals:2 * signals], np.std(np.arange(1, 21)))  # the wobble of 1..20
    assert np.allclose(features[2 * signals:], 20.0)  # +1 every 3 minutes = +20 per hour


def test_fault_windows_never_start_before_the_fault():
    window, step = 20, 10
    ends = list(window_ends(run_length=100, first_sample=21, window=window, step=step))
    assert ends[0] == 40  # the first window covers samples 21 to 40
    assert all(end - window + 1 >= 21 for end in ends)  # every window starts at or after sample 21
    assert ends[-1] <= 100  # and ends inside the run


def test_normal_windows_cover_the_whole_run():
    ends = list(window_ends(run_length=100, first_sample=1, window=20, step=10))
    assert ends == [20, 30, 40, 50, 60, 70, 80, 90, 100]


def test_the_classifier_sees_only_the_last_hour_before_now():
    table = episode_table(rising_run(30), now_sample=25)  # the episode shows samples 1 to 25
    features = episode_features(table)
    assert np.allclose(features[:len(SIGNALS)], 15.5)  # the average of samples 6 to 25: the last hour
