"""Chart: which signals carry the monitor's strangeness scores, in the hour after the first alarm.

Top: each signal's share of T² (strange amount). Bottom: its share of SPE (strange pattern).
Only the 8 biggest shares are drawn. The hour is the same one an episode ends with: from the
first alarm to "now". Change FAULT and RUN to look at other development runs.

Run it with:
    python -m plantagent.monitor.plot_contributions
The chart is saved in results/figures/.
"""

import matplotlib

matplotlib.use("Agg")  # draw straight into an image file, without opening a window
import matplotlib.pyplot as plt
import pandas as pd

from plantagent.config import PROJECT_ROOT
from plantagent.episodes.build import sample_time
from plantagent.monitor.contributions import contributions_of_run, hour_after_first_alarm, top_contributors
from plantagent.monitor.data import load_signals
from plantagent.monitor.scores import fit_monitor

FAULT = 4  # which fault's development run (1 to 20)
RUN = 1  # development runs 1 to 5
SHOWN = 8  # how many signals per panel

BAR_COLOUR = "#2a78d6"
INK, MUTED_INK, BACKGROUND = "#0b0b0b", "#52514e", "#fcfcfb"


def main() -> None:
    descriptions = dict(pd.read_csv(PROJECT_ROOT / "knowledge" / "tags.csv")[["tag", "description"]].values)
    monitor = fit_monitor()
    X = load_signals("dev", FAULT, {RUN})
    hour = hour_after_first_alarm(monitor, X)

    figure, panels = plt.subplots(2, 1, figsize=(10, 7.6))
    figure.patch.set_facecolor(BACKGROUND)
    for panel, (statistic, name) in zip(panels, (("T2", "Share of T² (strange amount)"),
                                                 ("SPE", "Share of SPE (strange pattern)"))):
        top = top_contributors(contributions_of_run(monitor, X[hour], statistic), SHOWN)[::-1]  # biggest on top
        labels = [f"{tag}  {descriptions[tag]}" for tag, _ in top]
        shares = [share * 100 for _, share in top]
        panel.set_facecolor(BACKGROUND)
        panel.barh(labels, shares, color=BAR_COLOUR, height=0.6)
        for y, share in enumerate(shares):
            panel.annotate(f"{share:.0f} %", xy=(share, y), xytext=(4, 0), textcoords="offset points",
                           va="center", color=INK, fontsize=9)
        panel.set_xlim(0, max(shares) * 1.2)
        panel.set_title(name, loc="left", color=INK, fontsize=11)
        panel.set_xlabel("% of the score, averaged over the hour", color=MUTED_INK)
        panel.tick_params(colors=MUTED_INK, labelsize=9)
        panel.tick_params(axis="y", length=0)
        for side in ("top", "right", "left"):
            panel.spines[side].set_visible(False)
        panel.spines["bottom"].set_color(MUTED_INK)
    figure.suptitle(f"Fault {FAULT}, development run {RUN}: from the first alarm ({sample_time(hour.start + 1)}) "
                    f"to one hour later ({sample_time(hour.stop)})", x=0.01, ha="left", color=INK, fontsize=12)
    figure.tight_layout()

    out_dir = PROJECT_ROOT / "results" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"contributions_fault{FAULT:02d}_run{RUN:02d}.png"
    figure.savefig(path, dpi=120)
    print(f"Chart saved: {path}")


if __name__ == "__main__":
    main()
