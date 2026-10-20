"""Draws project_leans.png from ../evidence/first_judge_pairs.csv and ../evidence/second_judge_pairs.csv.

Left panel: first judge, measurement runs only (the pilot is left out), pair verdicts per project.
Right panel: the 18 close-call pairs (pilot, run 1 and run 2 pairs with no one-sided must-pass failure),
first judge vs second judge on the same pairs.
Run: python project_leans.py   (needs matplotlib)
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
EV = HERE.parent / "evidence"
HARNESS, COMPARISON, TIE = "#2a78d6", "#eb6834", "#a3a29b"
INK, MUTED, SURFACE = "#1f1f1e", "#6b6a64", "#fcfcfb"
MEASUREMENT_RUN = {"A": "main", "B": "main", "C": "run2", "D": "run2", "E": "run3", "F": "run3"}
NAMES = {"A": "A  game-picker script", "B": "B  mood-logging app", "C": "C  note-filing analysis",
         "D": "D  route-planning tool", "E": "E  trading-research write-up", "F": "F  personal-records dashboard"}


def count(rows, key):
    c = {"harness": 0, "comparison": 0, "tie": 0}
    for r in rows:
        v = r[key]
        c["tie" if v in ("tie", "split") else v] += 1
    return c


first = [r for r in csv.DictReader(open(EV / "first_judge_pairs.csv", encoding="utf-8")) if r["status"] == "judged"]
second = list(csv.DictReader(open(EV / "second_judge_pairs.csv", encoding="utf-8")))

left = []
for p in "ABCDEF":
    left.append((NAMES[p], count([r for r in first if r["project"] == p and r["run"] == MEASUREMENT_RUN[p]], "pair_verdict")))
right = []
for p in "ABCD":
    rows = [r for r in second if r["project"] == p]
    right.append((NAMES[p] + "\nfirst judge", count(rows, "first_judge_verdict")))
    right.append(("second judge", count(rows, "second_judge_pair")))

fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), facecolor=SURFACE, gridspec_kw={"width_ratios": [1, 1]})


def draw(ax, data, title):
    ax.set_facecolor(SURFACE)
    ys = list(range(len(data)))[::-1]
    for y, (label, c) in zip(ys, data):
        # harness to the right of zero, comparison to the left, ties centred on zero in gray
        t = c["tie"]
        ax.barh(y, c["harness"], left=t / 2, color=HARNESS, height=0.62, edgecolor=SURFACE, linewidth=2)
        ax.barh(y, -c["comparison"], left=-t / 2, color=COMPARISON, height=0.62, edgecolor=SURFACE, linewidth=2)
        if t:
            ax.barh(y, t, left=-t / 2, color=TIE, height=0.62, edgecolor=SURFACE, linewidth=2)
        txt = f'{c["harness"]}-{c["comparison"]}' + (f'-{t}' if t else "")
        ax.text(c["harness"] + t / 2 + 0.15, y, txt, va="center", ha="left", fontsize=9, color=INK)
    ax.set_yticks(ys)
    ax.set_yticklabels([d[0] for d in data], fontsize=9, color=INK)
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlim(-4.5, 6.5)
    ax.set_xticks([-4, -2, 0, 2, 4, 6])
    ax.set_xticklabels(["4", "2", "0", "2", "4", "6"], fontsize=8, color=MUTED)
    ax.set_xlabel("pairs won by the comparison arm  |  pairs won by the harness arm", fontsize=9, color=MUTED)
    ax.set_title(title, fontsize=10.5, color=INK, loc="left")
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(length=0)


draw(axes[0], left, "First judge, all six projects (labels: harness-comparison-tie)")
draw(axes[1], right, "The 18 close-call pairs, first vs second judge")
handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (HARNESS, COMPARISON, TIE)]
fig.legend(handles, ["harness arm preferred", "comparison arm preferred", "tie or split between orders"],
           loc="lower center", ncol=3, frameon=False, fontsize=9)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(HERE / "project_leans.png", dpi=150, facecolor=SURFACE)
print("wrote", HERE / "project_leans.png")
