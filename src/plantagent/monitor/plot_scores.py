"""Chart: the monitor's two strangeness scores over time, for a normal run and a fault run.

Top: T² (strange amount). Bottom: SPE (strange pattern). The dashed line in each panel is the
alarm limit: only 1 % of healthy moments score above it. Change FAULT and RUN to look at
other development runs.

Run it with:
    python -m plantagent.monitor.plot_scores
The chart is saved in results/figures/.
"""

import matplotlib

matplotlib.use("Agg")  # draw straight into an image file, without opening a window
import matplotlib.pyplot as plt
import numpy as np

from plantagent.config import PROJECT_ROOT
from plantagent.monitor.data import load_signals
from plantagent.monitor.scores import fit_monitor, score_run

FAULT = 4  # which fault's development run to compare with normal operation (1 to 20)
RUN = 1  # development runs: 1 to 5 for faults (1 to 10 for normal operation)
FAULT_START_HOUR = 8

NORMAL_COLOUR, FAULT_COLOUR = "#2a78d6", "#eb6834"
INK, MUTED_INK, BACKGROUND = "#0b0b0b", "#52514e", "#fcfcfb"


def main() -> None:
    monitor = fit_monitor()
    normal_t2, normal_spe = score_run(monitor, load_signals("dev", 0, {RUN}))
    fault_t2, fault_spe = score_run(monitor, load_signals("dev", FAULT, {RUN}))
    hours = np.arange(1, len(normal_t2) + 1) * 3 / 60  # sample 1 is at 0:03

    panels_content = [
        ("T² (strange amount)", normal_t2, fault_t2, monitor["t2_limit"]),
        ("SPE (strange pattern)", normal_spe, fault_spe, monitor["spe_limit"]),
    ]
    figure, panels = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True)
    figure.patch.set_facecolor(BACKGROUND)
    for panel, (name, normal, faulty, limit) in zip(panels, panels_content):
        panel.set_facecolor(BACKGROUND)
        panel.plot(hours, normal, color=NORMAL_COLOUR, linewidth=1.1, label=f"normal run {RUN}")
        panel.plot(hours, faulty, color=FAULT_COLOUR, linewidth=1.1, label=f"fault {FAULT}, run {RUN}")
        panel.axhline(limit, color=MUTED_INK, linewidth=0.8, linestyle="--")
        panel.annotate(f"alarm limit {limit:.1f}", xy=(hours[-1], limit), xytext=(0, 6),
                       textcoords="offset points", ha="right", color=MUTED_INK, fontsize=9)
        panel.axvline(FAULT_START_HOUR, color=INK, linewidth=0.8)
        panel.set_ylim(bottom=0)
        panel.set_title(name, loc="left", color=INK, fontsize=11)
        panel.set_ylabel("score", color=MUTED_INK)
        panel.tick_params(colors=MUTED_INK)
        for side in ("top", "right"):
            panel.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            panel.spines[side].set_color(MUTED_INK)
    panels[0].legend(loc="upper left", frameon=False, labelcolor=INK)
    panels[-1].set_xlabel("hours since the start of the run", color=MUTED_INK)
    figure.tight_layout()

    out_dir = PROJECT_ROOT / "results" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"scores_fault{FAULT:02d}_run{RUN:02d}.png"
    figure.savefig(path, dpi=120)
    print(f"Chart saved: {path}")


if __name__ == "__main__":
    main()
