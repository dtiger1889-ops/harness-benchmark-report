"""Tally one or more judged runs: pair verdicts, project leans, the sign test, must-pass failures and tokens.

Usage: python tally.py RUN [RUN ...]
Reads results/<run>/judge_summary.json and results/v4-results.csv under the kit's root. Prints a report.

Rules (the ones the paper used):
  - pair verdict: a side wins a pair only when both presentation orders pick it; otherwise the pair is a tie
  - project lean: the arm with more pair wins in that project; equal = no lean
  - the only significance test is a two-sided exact sign test over the project leans (projects with no lean
    are left out); pooled pair counts are descriptive only, because repeats of one project are not independent
  - cost: total tokens (input + output + cache read + cache write) per trial, medians per arm per project, over
    the trials in judged pairs
"""
import csv
import json
import statistics
import sys
from math import comb
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kitconfig  # noqa: E402


def sign_test(k_harness: int, k_other: int) -> float:
    n, k = k_harness + k_other, min(k_harness, k_other)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main(runs: list[str]) -> int:
    rows = {r["trial_name"]: r for r in csv.DictReader(open(kitconfig.RESULTS / "v4-results.csv", encoding="utf-8"))}

    def total(name):
        r = rows[name]
        return sum(int(r[k]) for k in ("input", "output", "cache_read", "cache_create"))

    per_project = {}
    for run in runs:
        js = json.loads((kitconfig.RESULTS / run / "judge_summary.json").read_text(encoding="utf-8"))
        if js.get("shortfall"):
            print(f"[{run}] shortfall: {js['shortfall']}")
        for p in js["pairs"]:
            proj = per_project.setdefault(p["packet"], {"harness": 0, "bloat": 0, "tie": 0, "excluded": 0,
                                                         "tok_h": [], "tok_b": [], "mustpass": []})
            if "excluded" in p:
                proj["excluded"] += 1
                continue
            picks = {c["order"]: c["preference"] for c in p["calls"]}
            v = picks["xy"] if picks["xy"] == picks["yx"] else "tie"
            proj[{"x": "harness", "y": "bloat"}.get(v, "tie")] += 1
            proj["tok_h"].append(total(p["harness"]))
            proj["tok_b"].append(total(p["bloat"]))
            for c in p["calls"]:
                for side, arm in (("x", "harness"), ("y", "bloat")):
                    failed = ((c.get("critical") or {}).get(side) or {}).get("failed") or []
                    if failed:
                        proj["mustpass"].append(f"{p['harness'].rsplit('-', 1)[0]} {c['order']} {arm}: {' '.join(failed)}")
    leans = {}
    print("project  harness-bloat-tie  excluded  lean        tokens median harness / bloat (ratio)")
    for pid, d in sorted(per_project.items()):
        lean = "harness" if d["harness"] > d["bloat"] else "bloat" if d["bloat"] > d["harness"] else "none"
        leans[pid] = lean
        if d["tok_h"]:
            mh, mb = statistics.median(d["tok_h"]), statistics.median(d["tok_b"])
            tok = f"{mh:,.0f} / {mb:,.0f} ({mh / mb:.2f}x)"
        else:
            tok = "-"
        print(f"{pid:8} {d['harness']}-{d['bloat']}-{d['tie']:<14} {d['excluded']:<9} {lean:<11} {tok}")
        for m in d["mustpass"]:
            print(f"         must-pass failed: {m}")
    nh = sum(v == "harness" for v in leans.values())
    nb = sum(v == "bloat" for v in leans.values())
    print(f"\nproject leans: harness {nh}, bloat {nb}, none {len(leans) - nh - nb}")
    print(f"two-sided exact sign test on the {nh + nb} leaning projects: p = {sign_test(nh, nb):.4f}")
    pooled = {k: sum(d[k] for d in per_project.values()) for k in ("harness", "bloat", "tie")}
    print(f"pooled pairs (descriptive only, not tested): {pooled}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1:]))
