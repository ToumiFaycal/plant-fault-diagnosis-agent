"""Chart: how far some signals are from normal (their z-scores), in a normal run and in a fault run.

It uses the monitor's first stage (standardize.py): every value is measured in "normal wobbles".
Change FAULT, RUN and TAGS below to look at other development runs and other signals.

Run it with:
    python -m plantagent.monitor.plot_zscores
The chart is saved in results/figures/.
"""

import matplotlib

matplotlib.use("Agg")  # draw straight into an image file, without opening a window
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import SIGNALS, load_signals
from plantagent.monitor.standardize import fit_normal_stats, standardize

FAULT = 4  # which fault's development run to compare with normal operation (1 to 20)
RUN = 1  # development runs: 1 to 5 for faults (1 to 10 for normal operation)
TAGS = ["xmeas_9", "xmv_10"]  # the signals to draw, one panel each
FAULT_START_HOUR = 8  # in development and test runs, faults start 8 hours in

# Colours: the two lines in a fixed order (blue, then orange), plus text and background colours.
NORMAL_COLOUR, FAULT_COLOUR = "#2a78d6", "#eb6834"
INK, MUTED_INK, BACKGROUND = "#0b0b0b", "#52514e", "#fcfcfb"


def main() -> None:
    # Learn "normal" from the monitor's fitting runs, then measure both runs with that same ruler.
    splits = load_config()["splits"]
    averages, wobbles = fit_normal_stats(load_signals("train", 0, runs_between(splits["monitor_fit_runs"])))
    normal = standardize(load_signals("dev", 0, {RUN}), averages, wobbles)
    faulty = standardize(load_signals("dev", FAULT, {RUN}), averages, wobbles)

    hours = np.arange(1, len(normal) + 1) * 3 / 60  # sample 1 is at 0:03, sample 160 at 8:00
    descriptions = pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv").set_index("tag")["description"]

    figure, panels = plt.subplots(len(TAGS), 1, figsize=(10, 3.2 * len(TAGS)), sharex=True, sharey=True)
    figure.patch.set_facecolor(BACKGROUND)
    for panel, tag in zip(np.atleast_1d(panels), TAGS):
        column = SIGNALS.index(tag)
        panel.set_facecolor(BACKGROUND)
        panel.plot(hours, normal[:, column], color=NORMAL_COLOUR, linewidth=1.1, label=f"normal run {RUN}")
        panel.plot(hours, faulty[:, column], color=FAULT_COLOUR, linewidth=1.1, label=f"fault {FAULT}, run {RUN}")
        for level in (-3, 3):  # beyond these lines a value is "really unusual"
            panel.axhline(level, color=MUTED_INK, linewidth=0.8, linestyle="--")
        panel.axvline(FAULT_START_HOUR, color=INK, linewidth=0.8)
        panel.set_title(f"{descriptions[tag]} ({tag})", loc="left", color=INK, fontsize=11)
        panel.set_ylabel("z-score (normal wobbles)", color=MUTED_INK)
        panel.tick_params(colors=MUTED_INK)
        for side in ("top", "right"):
            panel.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            panel.spines[side].set_color(MUTED_INK)

    first = np.atleast_1d(panels)[0]
    first.legend(loc="upper left", frameon=False, labelcolor=INK)
    first.annotate("fault starts (8:00)", xy=(FAULT_START_HOUR, 0), xytext=(FAULT_START_HOUR + 0.6, 10.5),
                   color=INK, fontsize=9)
    first.annotate("±3: really unusual", xy=(hours[-1], 3), xytext=(hours[-1], 3.4), ha="right",
                   color=MUTED_INK, fontsize=9)
    np.atleast_1d(panels)[-1].set_xlabel("hours since the start of the run", color=MUTED_INK)
    figure.tight_layout()

    out_dir = PROJECT_ROOT / "results" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"zscores_fault{FAULT:02d}_run{RUN:02d}.png"
    figure.savefig(path, dpi=120)
    print(f"Chart saved: {path}")


if __name__ == "__main__":
    main()
