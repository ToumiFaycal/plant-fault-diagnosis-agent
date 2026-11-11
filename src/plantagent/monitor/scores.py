"""Stages 3 and 4 of the monitor: two strangeness scores for every moment, and an alarm limit for each.

Stage 3, the scores, built on the ways a healthy plant moves (found in stage 2):
  T² ("strange amount"): how far the moment goes along the kept ways, each measured in that way's
      own normal wobble, squared and added up. Big when the plant moves in its usual ways, but too far.
  SPE ("strange pattern"): how much of the moment the kept ways can't rebuild: the leftover.
      Big when the plant moves in a way a healthy plant doesn't.
Stage 4, the limits: on normal runs the monitor never learned from (the calibration runs), each
limit is placed so that only 1 % of healthy moments score above it.

Try it on the real data with:
    python -m plantagent.monitor.scores
"""

import numpy as np
from sklearn.decomposition import PCA

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import load_signals
from plantagent.monitor.patterns import choose_number_of_patterns, fit_patterns
from plantagent.monitor.standardize import fit_normal_stats, standardize


def t2_scores(Z: np.ndarray, patterns: PCA, kept: int) -> np.ndarray:
    """Strange amount (T²) of every moment: one number per row of Z.

    Z: standardized moments (rows) x signals (columns).
    patterns: the fitted PCA from stage 2.  kept: how many ways are kept (31 for the plant).
    """
    along = Z @ patterns.components_[:kept].T
    measured = along ** 2 / patterns.explained_variance_[:kept]
    return measured.sum(axis=1)


def spe_scores(Z: np.ndarray, patterns: PCA, kept: int) -> np.ndarray:
    """Strange pattern (SPE) of every moment: how much of it the kept ways can't rebuild."""
    along = Z @ patterns.components_[:kept].T
    rebuilt = along @ patterns.components_[:kept]
    leftover = Z - rebuilt
    return np.sum(leftover ** 2, axis=1)


def alarm_limit(healthy_scores: np.ndarray, percentile: float) -> float:
    """The score that only (100 - percentile) % of healthy moments go above, e.g. 1 % for 99."""
    return np.percentile(healthy_scores, percentile)

def fit_monitor() -> dict:
    """Learn everything the monitor needs from the normal training runs, in one go.

    Stages 1 and 2 on the fitting runs (1-100), then the two limits on the calibration runs (101-150).
    """
    config = load_config()
    splits, settings = config["splits"], config["monitor"]
    X = load_signals("train", 0, runs_between(splits["monitor_fit_runs"]))
    averages, wobbles = fit_normal_stats(X)
    patterns = fit_patterns(standardize(X, averages, wobbles))
    kept = choose_number_of_patterns(patterns.explained_variance_ratio_, settings["share_of_variation_to_keep"])

    Z_calibration = standardize(load_signals("train", 0, runs_between(splits["monitor_calibration_runs"])),
                                averages, wobbles)
    return {
        "averages": averages,
        "wobbles": wobbles,
        "patterns": patterns,
        "kept": kept,
        "t2_limit": alarm_limit(t2_scores(Z_calibration, patterns, kept), settings["alarm_percentile"]),
        "spe_limit": alarm_limit(spe_scores(Z_calibration, patterns, kept), settings["alarm_percentile"]),
        "calibration_moments": len(Z_calibration),
    }


def score_run(monitor: dict, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """T² and SPE of every moment of a run (raw signals in, two rows of scores out)."""
    Z = standardize(X, monitor["averages"], monitor["wobbles"])
    return t2_scores(Z, monitor["patterns"], monitor["kept"]), spe_scores(Z, monitor["patterns"], monitor["kept"])


def main() -> None:
    monitor = fit_monitor()
    print(f"Ways kept: {monitor['kept']}")
    print(f"Limits set on {monitor['calibration_moments']:,} healthy calibration moments:")
    print(f"  T² limit  {monitor['t2_limit']:6.1f}")
    print(f"  SPE limit {monitor['spe_limit']:6.1f}")

    print("\nShare of moments above the limits, development run 1, before and after 8:00:")
    for fault, name in ((0, "normal"), (4, "fault 4")):
        t2, spe = score_run(monitor, load_signals("dev", fault, {1}))
        before, after = slice(0, 160), slice(160, None)  # samples 1-160 are before the fault starts
        print(f"  {name:8} T² {np.mean(t2[before] > monitor['t2_limit']):6.1%} -> {np.mean(t2[after] > monitor['t2_limit']):6.1%}"
              f"   SPE {np.mean(spe[before] > monitor['spe_limit']):6.1%} -> {np.mean(spe[after] > monitor['spe_limit']):6.1%}")


if __name__ == "__main__":
    main()
