"""Tests for the monitor (src/plantagent/monitor/), on tiny hand-made tables."""

import numpy as np

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.patterns import choose_number_of_patterns, fit_patterns
from plantagent.monitor.standardize import fit_normal_stats, standardize


def fake_signals() -> np.ndarray:
    """4 moments (rows) x 2 signals (columns) on very different scales, like a pressure and a temperature."""
    return np.array([
        [2700.0, 120.38],
        [2710.0, 120.42],
        [2690.0, 120.40],
        [2720.0, 120.40],
    ])


def test_one_average_and_one_wobble_per_signal():
    averages, wobbles = fit_normal_stats(fake_signals())
    assert averages.shape == (2,)  # one number per signal (per column)
    assert wobbles.shape == (2,)
    assert np.allclose(averages, [2705.0, 120.40])  # "equal, up to tiny rounding errors"


def test_one_wobble_above_average_gives_z_of_1():
    averages, wobbles = fit_normal_stats(fake_signals())
    one_wobble_above = (averages + wobbles).reshape(1, -1)  # a table with a single moment
    assert np.allclose(standardize(one_wobble_above, averages, wobbles), [[1.0, 1.0]])


def test_standardized_fitting_data_has_average_0_and_wobble_1():
    X = fake_signals()
    averages, wobbles = fit_normal_stats(X)
    Z = standardize(X, averages, wobbles)
    assert Z.shape == X.shape
    assert np.allclose(Z.mean(axis=0), 0.0)
    assert np.allclose(Z.std(axis=0), 1.0)


def test_monitor_fitting_and_calibration_runs_never_overlap():
    # The alarm limits must be set on runs the monitor has never learned from.
    splits = load_config()["splits"]
    fitting = runs_between(splits["monitor_fit_runs"])
    calibration = runs_between(splits["monitor_calibration_runs"])
    assert fitting & calibration == set()


def test_two_signals_that_move_together_make_one_main_pattern():
    random = np.random.default_rng(0)  # made-up random numbers, the same every time the test runs
    pressure = random.normal(size=200)
    other_pressure = pressure + 0.01 * random.normal(size=200)  # follows the first one very closely
    shares = fit_patterns(np.column_stack([pressure, other_pressure])).explained_variance_ratio_
    assert shares[0] > 0.99  # one pattern ("both together") explains almost everything


def test_number_of_patterns_kept():
    shares = np.array([0.60, 0.25, 0.10, 0.05])
    assert choose_number_of_patterns(shares, 0.50) == 1  # 0.60 already reaches 50 %
    assert choose_number_of_patterns(shares, 0.90) == 3  # 0.60 + 0.25 = 0.85 isn't enough; + 0.10 = 0.95 is
    assert choose_number_of_patterns(shares, 0.99) == 4  # all four are needed
