"""Errors and cost per session, harness vs single file, paired within each judged pair.
Error = the session failed at least one must-pass check (as judged in either presentation order, or in both).
Cost = total tokens of the session. Reads the public evidence CSVs. Usage: py -3 -I errors_cost.py <evidence dir>"""
import csv
import math
import sys
from itertools import product
from pathlib import Path

ev = Path(sys.argv[1])
pairs = [r for r in csv.DictReader(open(ev / "first_judge_pairs.csv", encoding="utf-8")) if r["status"] == "judged"]
trials = list(csv.DictReader(open(ev / "trials.csv", encoding="utf-8")))
tok = {(t["pair"], t["arm"]): int(t["total_tokens"]) for t in trials}


def binom_two_sided(k, n):
    if n == 0:
        return 1.0
    k = max(k, n - k)
    tail = sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def signed_rank_p(diffs):
    d = [x for x in diffs if x != 0]
    n = len(d)
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    wpos = sum(r for r, x in zip(ranks, d) if x > 0)
    # exact null distribution by dynamic programming on doubled ranks
    dist = {0: 1}
    for r in ranks:
        r2 = int(round(r * 2))
        nd = {}
        for s, c in dist.items():
            nd[s] = nd.get(s, 0) + c
            nd[s + r2] = nd.get(s + r2, 0) + c
        dist = nd
    total = 2 ** n
    w2 = int(round(wpos * 2))
    mean2 = sum(int(round(r * 2)) for r in ranks) / 2
    dev = abs(w2 - mean2)
    p = sum(c for s, c in dist.items() if abs(s - mean2) >= dev - 1e-9) / total
    return wpos, n, p


def run(label, keep):
    rows = [r for r in pairs if keep(r)]
    for mode in ("either order", "both orders"):
        h_err = c_err = only_h = only_c = 0
        for r in rows:
            hf = [r["harness_mustpass_failed_h_first"].strip(), r["harness_mustpass_failed_c_first"].strip()]
            cf = [r["comparison_mustpass_failed_h_first"].strip(), r["comparison_mustpass_failed_c_first"].strip()]
            he = any(hf) if mode == "either order" else all(hf)
            ce = any(cf) if mode == "either order" else all(cf)
            h_err += he
            c_err += ce
            only_h += he and not ce
            only_c += ce and not he
        print(f"{label} | errors ({mode}): harness {h_err}/{len(rows)} sessions, single file {c_err}/{len(rows)}; "
              f"pairs where only harness erred {only_h}, only single file {only_c}; exact paired p = {binom_two_sided(only_h, only_h + only_c):.3f}")
    ratios = [tok[(r['pair'], 'harness')] / tok[(r['pair'], 'comparison')] for r in rows]
    logs = [math.log(x) for x in ratios]
    cheaper = sum(x < 1 for x in ratios)
    s = sorted(ratios)
    med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    hm = sorted(tok[(r['pair'], 'harness')] for r in rows)
    cm = sorted(tok[(r['pair'], 'comparison')] for r in rows)
    mid = lambda v: v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2
    w, n, p = signed_rank_p(logs)
    print(f"{label} | cost per session: median harness {mid(hm)/1e3:.0f}k vs single file {mid(cm)/1e3:.0f}k tokens; "
          f"paired ratio median {med:.2f}x (range {s[0]:.2f}-{s[-1]:.2f}); harness cheaper in {cheaper} of {len(rows)} pairs; "
          f"signed-rank on log ratio p = {p:.3f}; geometric-mean ratio {math.exp(sum(logs)/len(logs)):.2f}x")


run("Runs 1-3", lambda r: r["run"] != "pilot")
run("Pilot + runs 1-3", lambda r: True)
for p in "ABCDEF":
    run(f"Project {p}", lambda r, p=p: r["run"] != "pilot" and r["project"] == p)
