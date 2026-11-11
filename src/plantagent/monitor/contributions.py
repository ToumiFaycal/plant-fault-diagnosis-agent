"""Step 6.1: which signals make a moment strange (each signal's part of T² and of SPE).

The monitor's two scores say *how* strange a moment is, not *which* signals are to blame.
A contribution splits a score into 52 parts, one per signal, that add up to the score:
  SPE: the score is the leftover (what the healthy ways of moving can't rebuild), squared and
       added up over the signals. A signal's part is simply its own squared leftover.
  T²:  the score measures how far the moment goes along each kept way, in that way's own normal
       wobble. To share it out, turn those measurements back into the 52 signals (like "rebuilt"
       in SPE) and square each signal's piece. These parts also add up to T², and none is
       negative (the "complete decomposition" form named by Alcala and Qin, 2011).

Contributions are clues, not answers: they show where the strangeness appears, which is not
always where the fault started (the controllers spread a fault into the signals they move).

Try it on the real data with:
    python -m plantagent.monitor.contributions
"""

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.episodes.build import sample_time
from plantagent.monitor.alarms import alarm_run
from plantagent.monitor.data import SIGNALS, load_signals
from plantagent.monitor.scores import fit_monitor
from plantagent.monitor.standardize import standardize


def spe_contributions(Z: np.ndarray, patterns: PCA, kept: int) -> np.ndarray:
    """Each signal's part of SPE, at every moment: rows = moments, columns = signals.

    Adding up a row gives that moment's SPE score.
    """
    along = Z @ patterns.components_[:kept].T
    rebuilt = along @ patterns.components_[:kept]
    leftover = Z - rebuilt
    return leftover ** 2


def t2_contributions(Z: np.ndarray, patterns: PCA, kept: int) -> np.ndarray:
    """Each signal's part of T², at every moment: rows = moments, columns = signals.

    Adding up a row gives that moment's T² score, and no part is negative.
    """
    along = Z @ patterns.components_[:kept].T
    measured = along / np.sqrt(patterns.explained_variance_[:kept])
    back = measured @ patterns.components_[:kept]
    return back ** 2

def contributions_of_run(monitor: dict, X: np.ndarray, statistic: str) -> np.ndarray:
    """Raw signals in; each signal's part of "T2" or "SPE" at every moment out."""
    Z = standardize(X, monitor["averages"], monitor["wobbles"])
    if statistic == "T2":
        return t2_contributions(Z, monitor["patterns"], monitor["kept"])
    if statistic == "SPE":
        return spe_contributions(Z, monitor["patterns"], monitor["kept"])
    raise ValueError(f'statistic must be "T2" or "SPE", not {statistic!r}')


def top_contributors(contributions: np.ndarray, k: int) -> list[tuple[str, float]]:
    """The k signals with the biggest share of a score over a stretch of moments, biggest first.

    contributions: rows = moments, columns = the 52 signals (from one of the functions above).
    Returns (signal, share) pairs: a share of 0.44 means the signal carries 44 % of the score.
    """
    average = contributions.mean(axis=0)  # each signal's average part over the stretch
    shares = average / average.sum()
    biggest = np.argsort(shares)[::-1][:k]
    return [(SIGNALS[j], float(shares[j])) for j in biggest]


def hour_after_first_alarm(monitor: dict, X: np.ndarray) -> slice:
    """The moments an episode's last hour covers: from the first alarm to "now", one hour later."""
    config = load_config()
    first = int(np.flatnonzero(alarm_run(monitor, X, config["monitor"]["alarm_after_consecutive"]))[0])
    wait = config["episodes"]["investigate_after_minutes"] // 3  # 20 moments of 3 minutes
    return slice(first, first + wait + 1)  # positions count from 0: sample number = position + 1


def main() -> None:
    descriptions = dict(pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")[["tag", "description"]].values)
    monitor = fit_monitor()
    for fault in (4, 6):
        X = load_signals("dev", fault, {1})
        hour = hour_after_first_alarm(monitor, X)
        print(f"\nFault {fault}, development run 1, from the first alarm ({sample_time(hour.start + 1)}) "
              f"to one hour later ({sample_time(hour.stop)}):")
        for statistic in ("T2", "SPE"):
            print(f"  Biggest parts of {statistic}:")
            for tag, share in top_contributors(contributions_of_run(monitor, X[hour], statistic), 6):
                print(f"    {tag:9} {share:6.1%}  {descriptions[tag]}")


if __name__ == "__main__":
    main()
