"""Stage 5 of the monitor: when to actually sound the alarm.

A single moment above a limit happens about 2 % of the time even in a healthy plant (1 % for each
score), so alarming on one moment would cry wolf all day. The rule: alarm only when at least one of
the two scores stays above its limit for several moments in a row (set in config.toml).
"""

import numpy as np

from plantagent.monitor.scores import score_run


def above_a_limit(monitor: dict, X: np.ndarray) -> np.ndarray:
    """For every moment of a run: True if T² or SPE (or both) is above its limit."""
    t2, spe = score_run(monitor, X)
    return (t2 > monitor["t2_limit"]) | (spe > monitor["spe_limit"])


def consecutive_alarm(above: np.ndarray, in_a_row: int) -> np.ndarray:
    """For every moment: True if `above` has been True for at least `in_a_row` moments in a row,
    counting this one.

    Example with in_a_row = 2:
      above:  False  True  True  False  True  True  True
      alarm:  False  False True  False  False True  True
    """
    alarm = np.zeros(len(above), dtype=bool)
    streak = 0
    for i, is_above in enumerate(above):
        if is_above:
            streak += 1
        else:
            streak = 0
        alarm[i] = streak >= in_a_row
    return alarm


def alarm_run(monitor: dict, X: np.ndarray, in_a_row: int) -> np.ndarray:
    """For every moment of one run: is the monitor in alarm?"""
    return consecutive_alarm(above_a_limit(monitor, X), in_a_row)
