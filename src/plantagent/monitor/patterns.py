"""Stage 2 of the monitor: learn the plant's normal patterns (PCA).

A pattern is a recipe of signals that move together in normal operation, for example "reactor
pressure and separator pressure go up and down together". PCA finds these patterns in the normal
fitting runs, ranked from the one the plant uses most to the one it uses least, and says what
share of the normal variation each one explains. We keep the first patterns until they explain
the share set in config.toml (90 %).

Try it on the real data with:
    python -m plantagent.monitor.patterns
"""

import numpy as np
from sklearn.decomposition import PCA

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import load_signals
from plantagent.monitor.standardize import fit_normal_stats, standardize


def fit_patterns(Z: np.ndarray) -> PCA:
    """Find the patterns in standardized normal data (as many patterns as there are signals).

    The result holds, among other things:
      .explained_variance_ratio_  the share of normal variation each pattern explains, largest first
      .components_                the patterns themselves: one row per pattern, one number per signal
    """
    return PCA().fit(Z)


def choose_number_of_patterns(shares: np.ndarray, share_to_keep: float) -> int:
    """How many patterns to keep: the fewest, counted from the first, whose shares add up to share_to_keep.

    shares: the share of normal variation each pattern explains, largest first (they add up to 1).
    share_to_keep: for example 0.90 for 90 %.
    """
    running_total = 0
    for count, share in enumerate(shares, start=1):
        running_total += share
        if running_total >= share_to_keep:
            return count
    raise ValueError("share_to_keep is larger than the sum of shares")


def main() -> None:
    config = load_config()
    X = load_signals("train", 0, runs_between(config["splits"]["monitor_fit_runs"]))
    averages, wobbles = fit_normal_stats(X)
    patterns = fit_patterns(standardize(X, averages, wobbles))

    shares = patterns.explained_variance_ratio_
    print(f"PCA found {len(shares)} patterns in {X.shape[0]:,} normal moments.")
    print("Share of normal variation explained by the first five patterns:")
    for number, share in enumerate(shares[:5], start=1):
        print(f"  pattern {number}: {share:.1%}")

    share_to_keep = config["monitor"]["share_of_variation_to_keep"]
    kept = choose_number_of_patterns(shares, share_to_keep)
    print(f"\nPatterns kept to explain {share_to_keep:.0%} of normal variation: {kept} of {len(shares)}")


if __name__ == "__main__":
    main()
