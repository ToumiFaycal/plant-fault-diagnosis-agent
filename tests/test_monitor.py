"""Tests for the monitor (src/plantagent/monitor/), on tiny hand-made tables."""

import numpy as np

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.alarms import consecutive_alarm
from plantagent.monitor.contributions import spe_contributions, t2_contributions, top_contributors
from plantagent.monitor.data import SIGNALS
from plantagent.monitor.patterns import choose_number_of_patterns, fit_patterns
from plantagent.monitor.scores import alarm_limit, spe_scores, t2_scores
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


def twin_patterns():
    """The ways of moving of two made-up signals that always move together (like the two pressures)."""
    random = np.random.default_rng(1)
    first = random.normal(size=500)
    second = first + 0.05 * random.normal(size=500)
    Z = np.column_stack([first, second])
    return fit_patterns(Z - Z.mean(axis=0))  # way 1: "both together"; way 2: "apart" (almost never)


def test_a_moment_at_the_normal_average_is_not_strange():
    patterns = twin_patterns()
    at_average = np.array([[0.0, 0.0]])
    assert np.allclose(t2_scores(at_average, patterns, kept=1), 0)
    assert np.allclose(spe_scores(at_average, patterns, kept=1), 0)


def test_both_far_up_together_is_a_strange_amount_not_a_strange_pattern():
    patterns = twin_patterns()
    both_up = np.array([[2.0, 2.0]])  # the usual way of moving, but far
    assert t2_scores(both_up, patterns, kept=1)[0] > 1
    assert spe_scores(both_up, patterns, kept=1)[0] < 0.1


def test_moving_apart_is_a_strange_pattern_not_a_strange_amount():
    patterns = twin_patterns()
    apart = np.array([[2.0, -2.0]])  # one up, one down: the way a healthy pair never moves
    assert spe_scores(apart, patterns, kept=1)[0] > 1
    assert t2_scores(apart, patterns, kept=1)[0] < 0.1


def test_alarm_limit_leaves_1_percent_of_healthy_scores_above_it():
    healthy_scores = np.arange(1, 1001)  # 1, 2, ..., 1000
    limit = alarm_limit(healthy_scores, 99)
    assert np.mean(healthy_scores > limit) == 0.01  # exactly 10 of the 1000 are above


def test_alarm_only_after_enough_moments_in_a_row():
    above = np.array([False, True, True, False, True, True, True])
    assert list(consecutive_alarm(above, 1)) == [False, True, True, False, True, True, True]
    assert list(consecutive_alarm(above, 2)) == [False, False, True, False, False, True, True]
    assert list(consecutive_alarm(above, 3)) == [False, False, False, False, False, False, True]


def test_a_streak_broken_by_one_normal_moment_starts_again():
    above = np.array([True, True, False, True, True])
    assert not consecutive_alarm(above, 3).any()  # never 3 in a row


# --- Contributions: each signal's part of a score ---

def twins_and_loner_patterns():
    """Three made-up signals: the first two always move together (twins), the third on its own.
    Kept ways: "twins together" and "the loner"; left out: "twins apart" (almost never happens)."""
    random = np.random.default_rng(2)
    first = random.normal(size=1000)
    second = first + 0.05 * random.normal(size=1000)
    loner = random.normal(size=1000)
    Z = np.column_stack([first, second, loner])
    return fit_patterns(Z - Z.mean(axis=0))


def test_contributions_add_up_to_the_scores():
    patterns = twins_and_loner_patterns()
    moments = np.random.default_rng(3).normal(size=(5, 3)) * 3  # 5 random moments
    assert spe_contributions(moments, patterns, kept=2).shape == (5, 3)  # one part per moment and signal
    assert np.allclose(spe_contributions(moments, patterns, kept=2).sum(axis=1), spe_scores(moments, patterns, kept=2))
    assert np.allclose(t2_contributions(moments, patterns, kept=2).sum(axis=1), t2_scores(moments, patterns, kept=2))
    assert (t2_contributions(moments, patterns, kept=2) >= 0).all()  # no negative parts


def test_a_signal_far_out_on_its_own_carries_the_t2():
    patterns = twins_and_loner_patterns()
    loner_far_up = np.array([[0.0, 0.0, 4.0]])
    parts = t2_contributions(loner_far_up, patterns, kept=2)[0]
    assert parts[2] / parts.sum() > 0.95  # the loner carries almost all of T²


def test_twins_moving_apart_share_the_spe():
    patterns = twins_and_loner_patterns()
    apart = np.array([[2.0, -2.0, 0.0]])  # the twins break their pattern; the loner is calm
    shares = spe_contributions(apart, patterns, kept=2)[0] / spe_scores(apart, patterns, kept=2)[0]
    assert np.allclose(shares, [0.5, 0.5, 0.0], atol=0.05)  # the blame is shared by the two twins


def test_top_contributors_are_ranked_by_their_average_share():
    parts = np.zeros((2, len(SIGNALS)))
    parts[:, SIGNALS.index("xmeas_9")] = [1.0, 1.0]  # average 1
    parts[:, SIGNALS.index("xmv_10")] = [3.0, 5.0]  # average 4
    top = top_contributors(parts, k=2)
    assert [tag for tag, _ in top] == ["xmv_10", "xmeas_9"]  # biggest first
    assert np.allclose([share for _, share in top], [0.8, 0.2])  # 4 of 5 and 1 of 5
