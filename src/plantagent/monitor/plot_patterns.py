"""Chart: the plant's normal patterns, in two pictures.

Left: reactor pressure against separator pressure for every normal moment. They move together,
so the dots form a thin stripe: that stripe is one pattern.
Right: how much of the normal variation the first patterns explain, added up pattern by pattern,
with the 90 % line and the number of patterns kept.

Run it with:
    python -m plantagent.monitor.plot_patterns
The chart is saved in results/figures/.
"""

import matplotlib

matplotlib.use("Agg")  # draw straight into an image file, without opening a window
import matplotlib.pyplot as plt
import numpy as np

from plantagent.config import PROJECT_ROOT, load_config
from plantagent.convert_data import runs_between
from plantagent.monitor.data import SIGNALS, load_signals
from plantagent.monitor.patterns import choose_number_of_patterns, fit_patterns
from plantagent.monitor.standardize import fit_normal_stats, standardize

PAIR = ("xmeas_7", "xmeas_13")  # reactor pressure and separator pressure

COLOUR = "#2a78d6"
INK, MUTED_INK, BACKGROUND = "#0b0b0b", "#52514e", "#fcfcfb"


def main() -> None:
    config = load_config()
    X = load_signals("train", 0, runs_between(config["splits"]["monitor_fit_runs"]))
    averages, wobbles = fit_normal_stats(X)
    Z = standardize(X, averages, wobbles)
    shares = fit_patterns(Z).explained_variance_ratio_
    share_to_keep = config["monitor"]["share_of_variation_to_keep"]
    kept = choose_number_of_patterns(shares, share_to_keep)

    figure, (left, right) = plt.subplots(1, 2, figsize=(12, 5))
    figure.patch.set_facecolor(BACKGROUND)

    # Left: one dot per normal moment.
    x, y = Z[:, SIGNALS.index(PAIR[0])], Z[:, SIGNALS.index(PAIR[1])]
    left.scatter(x, y, s=2, alpha=0.15, color=COLOUR, linewidths=0)
    left.set_title("Reactor and separator pressure, every normal moment", loc="left", color=INK, fontsize=11)
    left.set_xlabel(f"reactor pressure, {PAIR[0]} (z-score)", color=MUTED_INK)
    left.set_ylabel(f"separator pressure, {PAIR[1]} (z-score)", color=MUTED_INK)
    left.set_aspect("equal")
    left.annotate(f"correlation {np.corrcoef(x, y)[0, 1]:+.3f}", xy=(0.03, 0.93), xycoords="axes fraction",
                  color=INK, fontsize=9)

    # Right: running total of the shares, pattern by pattern.
    counts = np.arange(1, len(shares) + 1)
    right.plot(counts, np.cumsum(shares) * 100, color=COLOUR, linewidth=2, marker="o", markersize=3)
    right.axhline(share_to_keep * 100, color=MUTED_INK, linewidth=0.8, linestyle="--")
    right.axvline(kept, color=INK, linewidth=0.8)
    right.annotate(f"{kept} patterns kept for {share_to_keep:.0%}", xy=(kept, 50), xytext=(kept + 1, 45),
                   color=INK, fontsize=9)
    right.set_title("Share of normal variation explained, adding patterns one by one", loc="left",
                    color=INK, fontsize=11)
    right.set_xlabel("number of patterns kept", color=MUTED_INK)
    right.set_ylabel("share of normal variation explained (%)", color=MUTED_INK)
    right.set_ylim(0, 100)

    for panel in (left, right):
        panel.set_facecolor(BACKGROUND)
        panel.tick_params(colors=MUTED_INK)
        for side in ("top", "right"):
            panel.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            panel.spines[side].set_color(MUTED_INK)
    figure.tight_layout()

    out_dir = PROJECT_ROOT / "results" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "normal_patterns.png"
    figure.savefig(path, dpi=120)
    print(f"Chart saved: {path}")


if __name__ == "__main__":
    main()
