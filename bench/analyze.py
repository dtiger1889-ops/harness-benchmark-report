#!/usr/bin/env python3
"""
analyze.py — Harness Benchmark Analyzer
Reads results.csv (default: alongside this script) and produces paired
H0-vs-H1 statistics.
Usage: python analyze.py [--csv path/to/results.csv] [--plot]
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

BENCH_ROOT = Path(__file__).resolve().parent

try:
    from scipy import stats
    import numpy as np
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("WARNING: scipy/numpy not installed. Running descriptive stats only.")
    print("Install with: pip install scipy numpy\n")

try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


METRICS = [
    'total_input', 'total_output', 'cache_read', 'cache_create',
    'peak_context', 'turn_count', 'turn_logical', 'duration_s',
]


def load_results(csv_path: Path) -> list[dict]:
    rows = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            for m in METRICS + ['trial_num', 'compaction_events']:
                try:
                    row[m] = float(row[m])
                except (ValueError, KeyError):
                    row[m] = None
            row['passed'] = int(row.get('passed', -1))
            rows.append(row)
    return rows


def pair_trials(rows: list[dict]) -> dict[str, dict[int, dict]]:
    """Returns {task: {trial_num: {'H0': row, 'H1': row}}}"""
    paired = defaultdict(lambda: defaultdict(dict))
    for r in rows:
        paired[r['task']][int(r['trial_num'])][r['condition']] = r
    return paired


def analyze_task(task: str, pairs: dict[int, dict]) -> None:
    print(f"\n{'='*60}")
    print(f"Task {task}  ({len(pairs)} pairs)")
    print(f"{'='*60}")

    h0_vals = defaultdict(list)
    h1_vals = defaultdict(list)
    matched_pairs = defaultdict(list)  # metric -> list of (h0, h1) tuples

    h0_pass = h1_pass = 0
    h0_count = h1_count = 0

    for trial_num in sorted(pairs.keys()):
        pair = pairs[trial_num]
        h0 = pair.get('H0')
        h1 = pair.get('H1')
        if h0:
            h0_count += 1
            if h0['passed'] == 1: h0_pass += 1
        if h1:
            h1_count += 1
            if h1['passed'] == 1: h1_pass += 1
        if h0 and h1:
            for m in METRICS:
                if h0[m] is not None and h1[m] is not None:
                    h0_vals[m].append(h0[m])
                    h1_vals[m].append(h1[m])
                    matched_pairs[m].append((h0[m], h1[m]))

    # Success rate
    print(f"\nSuccess rate:")
    print(f"  H0: {h0_pass}/{h0_count}  H1: {h1_pass}/{h1_count}")

    # Descriptive + Wilcoxon per metric
    print(f"\n{'Metric':<20} {'H0 median':>12} {'H1 median':>12} {'H1-H0 diff%':>12} {'p-value':>10} {'sig':>5}")
    print(f"{'-'*73}")
    for m in METRICS:
        if not matched_pairs[m]:
            continue
        h0_arr = [p[0] for p in matched_pairs[m]]
        h1_arr = [p[1] for p in matched_pairs[m]]
        h0_med = sorted(h0_arr)[len(h0_arr)//2]
        h1_med = sorted(h1_arr)[len(h1_arr)//2]
        pct = ((h1_med - h0_med) / h0_med * 100) if h0_med != 0 else float('nan')
        if HAS_SCIPY and len(h0_arr) >= 3:
            try:
                _, p = stats.wilcoxon(h0_arr, h1_arr, alternative='greater')
                sig = '***' if p < 0.001 else ('**' if p < 0.01 else ('*' if p < 0.05 else ''))
                p_str = f'{p:.4f}'
            except Exception:
                p_str, sig = 'n/a', ''
        else:
            p_str, sig = f'n<3' if len(h0_arr) < 3 else 'no scipy', ''
        print(f"{m:<20} {h0_med:>12.0f} {h1_med:>12.0f} {pct:>+11.1f}% {p_str:>10} {sig:>5}")

    print(f"\n  Decision rule: reject H0 if p<0.05 AND H1 median lower AND H1 success ≥ H0 success")


def plot_context_growth(task: str, pairs: dict[int, dict], out_dir: Path) -> None:
    """Placeholder: per-turn context curves require raw JSONL re-parse (not in results.csv)."""
    print(f"  [plot] Context growth curves require re-parsing session JSONLs — see parse_jsonl_curves().")


def parse_jsonl_curves(trial_dir: Path) -> list[int]:
    """Parse a single session.jsonl and return per-turn context sizes."""
    import json
    session = trial_dir / 'session.jsonl'
    if not session.exists():
        return []
    curves = []
    for line in session.read_text(encoding='utf-8').splitlines():
        try:
            obj = json.loads(line)
        except Exception:
            continue
        msg = obj.get('message') or (obj if obj.get('type') == 'assistant' else None)
        if not msg:
            continue
        u = msg.get('usage', {})
        inp = int(u.get('input_tokens', 0) or 0)
        cr  = int(u.get('cache_read_input_tokens', 0) or 0)
        cc  = int(u.get('cache_creation_input_tokens', 0) or 0)
        if inp + cr + cc > 0:
            curves.append(inp + cr + cc)
    return curves


def plot_all_curves(pairs: dict[int, dict], task: str, out_dir: Path) -> None:
    if not HAS_MATPLOTLIB:
        print("  matplotlib not installed — skipping plots.")
        return
    fig, ax = plt.subplots(figsize=(10, 5))
    for trial_num, pair in sorted(pairs.items()):
        for cond, color in [('H0', 'tomato'), ('H1', 'steelblue')]:
            row = pair.get(cond)
            if not row:
                continue
            trial_dir = BENCH_ROOT / 'trials' / row['trial_name']
            curve = parse_jsonl_curves(trial_dir)
            if curve:
                ax.plot(range(len(curve)), curve, color=color, alpha=0.4,
                        label=cond if trial_num == 1 else '_nolegend_')
    ax.set_title(f'Context growth — Task {task}')
    ax.set_xlabel('Turn')
    ax.set_ylabel('Prompt tokens (input+cache)')
    handles = [plt.Line2D([0],[0],color='tomato',label='H0 (no harness)'),
               plt.Line2D([0],[0],color='steelblue',label='H1 (harness)')]
    ax.legend(handles=handles)
    out = out_dir / f'context_growth_task{task}.png'
    fig.savefig(out, dpi=120, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {out}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', default=str(BENCH_ROOT / 'results.csv'))
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"results.csv not found at {csv_path}")
        sys.exit(1)

    rows = load_results(csv_path)
    paired = pair_trials(rows)

    for task in sorted(paired.keys()):
        analyze_task(task, paired[task])
        if args.plot:
            out_dir = BENCH_ROOT / 'results'
            out_dir.mkdir(exist_ok=True)
            plot_all_curves(paired[task], task, out_dir)

    print('\nDone.')


if __name__ == '__main__':
    main()
