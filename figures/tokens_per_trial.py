"""Draws tokens_per_trial.png from ../evidence/trials.csv.

One row per project (runs 1-3; the pilot is left out), one dot per worker trial, total tokens
(input + output + cache read + cache write). Filled dots are trials in judged pairs; hollow dots are
voided trials or the unvoided half of a voided pair. The short vertical bar is the median of the
filled dots for that arm.
Run: python tokens_per_trial.py   (needs matplotlib)
"""
import csv
import statistics
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
EV = HERE.parent / "evidence"
COLOR = {"harness": "#2a78d6", "comparison": "#eb6834"}
INK, MUTED, SURFACE = "#1f1f1e", "#6b6a64", "#fcfcfb"
NAMES = {"A": "A  game-picker script", "B": "B  mood-logging app", "C": "C  note-filing analysis",
         "D": "D  route-planning tool", "E": "E  trading-research write-up", "F": "F  personal-records dashboard"}

rows = [r for r in csv.DictReader(open(EV / "trials.csv", encoding="utf-8")) if r["run"] != "pilot"]
fig, ax = plt.subplots(figsize=(11, 5.6), facecolor=SURFACE)
ax.set_facecolor(SURFACE)
ys = {}
for i, p in enumerate("ABCDEF"):
    base = (5 - i) * 1.0
    for arm, off in (("harness", 0.17), ("comparison", -0.17)):
        y = base + off
        ys[(p, arm)] = y
        sel = [r for r in rows if r["project"] == p and r["arm"] == arm]
        judged = [int(r["total_tokens"]) / 1e6 for r in sel if r["in_judged_pair"] == "1"]
        other = [int(r["total_tokens"]) / 1e6 for r in sel if r["in_judged_pair"] != "1"]
        ax.scatter(judged, [y] * len(judged), s=46, color=COLOR[arm], edgecolor=COLOR[arm], linewidth=1.5, zorder=3)
        ax.scatter(other, [y] * len(other), s=46, facecolor="none", edgecolor=COLOR[arm], linewidth=1.5, zorder=3)
        if judged:
            m = statistics.median(judged)
            ax.plot([m, m], [y - 0.13, y + 0.13], color=INK, linewidth=2, zorder=4)
ax.set_yticks([(5 - i) * 1.0 for i in range(6)])
ax.set_yticklabels([NAMES[p] for p in "ABCDEF"], fontsize=9, color=INK)
ax.set_xlabel("total tokens per worker trial, millions (input + output + cache read + cache write)", fontsize=9, color=MUTED)
ax.set_xlim(left=0)
ax.grid(axis="x", color="#e4e3dd", linewidth=0.8, zorder=0)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.spines["bottom"].set_color(MUTED)
ax.tick_params(length=0, labelsize=8, colors=MUTED)
ax.tick_params(axis="y", colors=INK)
h = [plt.Line2D([], [], marker="o", linestyle="", color=COLOR["harness"], markersize=7, label="harness arm (upper dot row)"),
     plt.Line2D([], [], marker="o", linestyle="", color=COLOR["comparison"], markersize=7, label="comparison arm (lower dot row)"),
     plt.Line2D([], [], marker="o", linestyle="", markerfacecolor="none", markeredgecolor=MUTED, markersize=7, label="voided, or partner voided"),
     plt.Line2D([], [], color=INK, linewidth=2, label="median of judged trials")]
fig.legend(handles=h, loc="lower center", ncol=4, frameon=False, fontsize=8.5)
ax.set_title("Total tokens per trial by project and arm (runs 1-3)", fontsize=10.5, color=INK, loc="left")
fig.tight_layout(rect=(0, 0.06, 1, 1))
fig.savefig(HERE / "tokens_per_trial.png", dpi=150, facecolor=SURFACE)
print("wrote", HERE / "tokens_per_trial.png")
