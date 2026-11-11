"""Baseline B2: a classifier that learns to name the fault from labelled examples.

This is the project's equivalent of the YOLO model in my first project: shown many examples with
the answer attached, it learns which numbers go with which answer. Nothing else: no tools,
no documents, no reasoning, no explanation.

What it looks at: the last hour of the plant (20 moments), summed up per signal by three numbers:
  - the average over the hour;
  - the wobble (standard deviation) over the hour;
  - the slope: how fast the signal rises (+) or falls (-), in its own unit per hour.
52 signals x 3 = 156 numbers per hour. The numbers a model decides from are called "features".

What it learns from: training runs 1-50 of the normal plant and of each of the 20 faults (training
runs only, never development or test runs), one 1-hour window every 30 minutes. In fault runs only
windows that start at or after the fault's start are used: before it, the plant is still healthy,
and labelling that hour "fault" would teach the classifier something false.

The model: a random forest (scikit-learn). Many decision trees, each grown on a random part of the
examples, vote. A tree is a chain of yes/no questions such as "is the wobble of xmeas_9 above 0.05?",
ending in an answer. The share of trees voting for each answer is its probability.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from plantagent.config import load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import SIGNALS, load_signals_by_run

MINUTES_PER_SAMPLE = 3


def window_features(window: np.ndarray) -> np.ndarray:
    """156 numbers that sum up a window (rows = moments, columns = the 52 signals):
    the 52 averages, then the 52 wobbles, then the 52 slopes (per hour)."""
    hours = np.arange(len(window)) * MINUTES_PER_SAMPLE / 60
    hours_from_middle = hours - hours.mean()
    average = window.mean(axis=0)
    wobble = window.std(axis=0)
    # Slope of the best straight line through each signal (least squares): how much it changes per hour.
    slope = hours_from_middle @ (window - average) / (hours_from_middle @ hours_from_middle)
    return np.concatenate([average, wobble, slope])


def window_ends(run_length: int, first_sample: int, window: int, step: int) -> range:
    """Sample numbers where training windows end, for one run.

    Every window covers `window` moments and starts at or after `first_sample`
    (1 for a normal run, the first faulty sample for a fault run).
    """
    return range(first_sample + window - 1, run_length + 1, step)


def training_set() -> tuple[np.ndarray, np.ndarray]:
    """All training windows as features (rows = windows, 156 columns) and their answers (0 to 20)."""
    config = load_config()
    settings = config["baseline"]
    window = settings["window_minutes"] // MINUTES_PER_SAMPLE
    step = settings["window_every_minutes"] // MINUTES_PER_SAMPLE
    first_faulty = config["data"]["first_faulty_sample_training"]
    features, answers = [], []
    for fault in range(0, 21):
        for X in load_signals_by_run("train", fault, runs_between(config["splits"]["baseline_runs"])).values():
            first_sample = 1 if fault == 0 else first_faulty
            for end in window_ends(len(X), first_sample, window, step):
                features.append(window_features(X[end - window:end]))
                answers.append(fault)
    return np.array(features), np.array(answers)


def train_classifier(features: np.ndarray, answers: np.ndarray) -> RandomForestClassifier:
    settings = load_config()["baseline"]
    model = RandomForestClassifier(n_estimators=settings["trees"], min_samples_leaf=settings["min_examples_per_leaf"],
                                   random_state=settings["seed"], n_jobs=2)  # 2 cores: keeps memory use low
    return model.fit(features, answers)


def episode_features(table: pd.DataFrame) -> np.ndarray:
    """The features of an episode: its last hour, up to "now" (the last row the episode shows)."""
    window = load_config()["baseline"]["window_minutes"] // MINUTES_PER_SAMPLE
    return window_features(table[SIGNALS].to_numpy()[-window:])
