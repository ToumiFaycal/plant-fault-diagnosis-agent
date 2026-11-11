"""Open one episode: the only plant data the server ever reads.

Reads two things, and nothing else:
  - one line of the episode list (episodes/dev.jsonl): the trigger message and "now";
  - the episode's own signal file (data/episodes/<name>.parquet): sample, clock time, 52 signals.
The answer key is a different file, and this code can't open it: only the "dev" and "test"
episode lists are accepted.
"""

import json
from dataclasses import dataclass

import pandas as pd

from plantagent.config import PROJECT_ROOT, load_config

EPISODE_LISTS = ("dev", "test")


@dataclass(frozen=True)
class Episode:
    name: str
    trigger_message: str
    now_sample: int
    table: pd.DataFrame  # rows = moments 1..now; columns: sample, sample_time, the 52 signals


def load_episode(name: str, split: str = "dev") -> Episode:
    """Open the episode called `name` from the "dev" or "test" episode list."""
    if split not in EPISODE_LISTS:
        raise ValueError(f"split must be one of {EPISODE_LISTS}, not {split!r}")
    lines = (PROJECT_ROOT / "episodes" / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines if line.strip()]
    entry = next((e for e in entries if e["episode"] == name), None)
    if entry is None:
        raise ValueError(f"No episode called {name!r} in episodes/{split}.jsonl")

    table = pd.read_parquet(PROJECT_ROOT / load_config()["data"]["episodes_dir"] / f"{name}.parquet")
    table = table[table["sample"] <= entry["now_sample"]]  # a second safety: nothing after now, ever
    return Episode(name=name, trigger_message=entry["trigger_message"], now_sample=entry["now_sample"], table=table)
