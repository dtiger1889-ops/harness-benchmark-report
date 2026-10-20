"""Planning sensitivity, not a new benchmark result. Standard library only.

Run: python evidence/feasibility.py --output evidence/feasibility.json
Binary power enumerates the exact paired test under hypothetical joint error
rates. Session calculations assume independent pairs and do not generalize over
projects. Cost planning reuses historical variation as a sensitivity assumption.
"""
import argparse
import csv
import json
import math
import random
import statistics as st
from functools import lru_cache
from pathlib import Path


def binom(n, p):
    if p == 0:
        return [1.0] + [0.0] * n
    if p == 1:
        return [0.0] * n + [1.0]
    return [math.exp(math.lgamma(n + 1) - math.lgamma(k + 1)
                     - math.lgamma(n - k + 1) + k * math.log(p)
                     + (n - k) * math.log1p(-p)) for k in range(n + 1)]


@lru_cache(None)
def critical(m):
    # Exact two-sided binomial null p <= .05, favorable direction only.
    tail = 0
    cutoff = m + 1
    for k in range(m, m // 2, -1):
        tail += math.comb(m, k)
        if 40 * tail <= 2 ** m:
            cutoff = k
        else:
            break
    return cutoff


@lru_cache(None)
def conditional_power(m, q):
    return sum(binom(m, q)[critical(m):])


def power(n, none_only, harness_only):
    discordance = none_only + harness_only
    if discordance == 0:
        return 0.0
    q = none_only / discordance
    return sum(p * conditional_power(m, q)
               for m, p in enumerate(binom(n, discordance)))


def first_80(a, b):
    # First crossing, not a guarantee for every larger n: exact power is discrete.
    return next((n for n in range(1, 1001) if power(n, a, b) >= .8), None)


def load_evidence(ev):
    with (ev / 'trials.csv').open(encoding='utf-8') as f:
        trials = list(csv.DictReader(f))
    with (ev / 'first_judge_pairs.csv').open(encoding='utf-8') as f:
        pairs = [r for r in csv.DictReader(f)
                 if r['status'] == 'judged' and r['run'] != 'pilot']
    return trials, pairs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    ev = Path(__file__).resolve().parent
    trials, pairs = load_evidence(ev)
    tokens = {(r['pair'], r['arm']): int(r['total_tokens']) for r in trials}
    by_project = {p: [] for p in 'ABCDEF'}
    only_h = only_c = errors_h = errors_c = 0
    for row in pairs:
        he = any(row[k].strip() for k in
                 ('harness_mustpass_failed_h_first', 'harness_mustpass_failed_c_first'))
        ce = any(row[k].strip() for k in
                 ('comparison_mustpass_failed_h_first', 'comparison_mustpass_failed_c_first'))
        errors_h += he
        errors_c += ce
        only_h += he and not ce
        only_c += ce and not he
        by_project[row['project']].append(math.log(
            tokens[row['pair'], 'harness'] / tokens[row['pair'], 'comparison']))
    logs = [x for values in by_project.values() for x in values]
    sd = st.stdev(logs)
    scenarios = [
        ('historical organization comparison (sensitivity only)', only_c / len(pairs), only_h / len(pairs)),
        ('10 percentage point reduction', .20, .10),
        ('25 percentage point reduction', .30, .05),
        ('40 percentage point reduction', .45, .05),
        ('50 percentage point reduction, no reverse failures', .50, .00),
    ]
    binary = [{
        'scenario': label, 'none_only_error_probability': a,
        'harness_only_error_probability': b, 'absolute_error_reduction': a - b,
        'power_12_pairs': power(12, a, b), 'power_24_pairs': power(24, a, b),
        'first_pairs_at_80_percent_power': first_80(a, b),
    } for label, a, b in scenarios]
    # A separate scenario: six independent, non-tied project leans.
    project = [{'true_probability_project_leans_harness': q,
                'power_six_projects': conditional_power(6, q),
                'first_non_tied_projects_at_80_percent_power': first_80(q, 1 - q)}
               for q in (.6, .7, .8, .9)]
    # Hypothetical one-sided t test on log cost, alpha .05. This is NOT the
    # existing signed-rank analysis or a newly adopted acceptance rule.
    rng = random.Random(20261020)
    simulations = 20000
    cost = []
    for n, t95 in ((12, 1.795884819), (24, 1.713871528)):
        for true_ratio in (1.0, .9, .8, .7):
            for margin in (1.0, 1.1):
                successes = 0
                for _ in range(simulations):
                    sample = [rng.gauss(math.log(true_ratio), sd) for _ in range(n)]
                    upper = st.mean(sample) + t95 * st.stdev(sample) / math.sqrt(n)
                    successes += upper < math.log(margin)
                cost.append({'pairs': n, 'true_geometric_mean_ratio': true_ratio,
                             'upper_ratio_limit_to_establish': margin,
                             'estimated_power': successes / simulations})
    workload = {}
    for arm in ('harness', 'comparison'):
        medians = {}
        for p in 'ABCDEF':
            values = [int(t['total_tokens']) for t in trials if t['run'] != 'pilot'
                      and t['project'] == p and t['arm'] == arm and t['in_judged_pair'] == '1']
            medians[p] = st.median(values)
        workload[arm] = {'historical_medians_by_project': medians,
                         'two_sessions_per_project_reference_tokens': 2 * sum(medians.values())}
    project_means = [st.mean(v) for v in by_project.values()]
    project_se = st.stdev(project_means) / math.sqrt(6)
    result = {
        'description': '2026-10-20 planning sensitivity; no no-notes trials run',
        'assumptions': {'two_sided_error_test_alpha': .05, 'target_power': .8,
                        'independent_pairs_only_for_session_scenarios': True,
                        'no_notes_effect_unknown': True, 'cost_mc_repetitions': simulations,
                        'cost_mc_seed': 20261020, 'cost_mc_max_standard_error': .5 / math.sqrt(simulations)},
        'historical': {'pairs': len(pairs), 'harness_error_sessions': errors_h,
                       'comparison_error_sessions': errors_c, 'harness_only_errors': only_h,
                       'comparison_only_errors': only_c, 'sd_log_paired_cost': sd,
                       'equal_weight_project_geometric_ratio': math.exp(st.mean(project_means)),
                       'project_t95_interval': [math.exp(st.mean(project_means) - 2.570581836 * project_se),
                                                math.exp(st.mean(project_means) + 2.570581836 * project_se)]},
        'exact_binary_power': binary, 'project_sign_test_power': project,
        'paired_error_significance_minimum_favorable_counts': {str(m): critical(m) for m in range(6, 13)},
        'cost_sensitivity_iid_lognormal_one_sided_t': cost,
        'reference_worker_workload_not_subscription_forecast': workload,
        'planned_invocations_without_replacements_or_retries': {
            'workers': 24, 'calibration_judges': 60, 'pair_judges': 24, 'fact_diagnostics': 24},
    }
    # Boundary checks and independent finite enumeration of the 6-pair case.
    assert critical(5) == 6 and critical(6) == 6 and critical(12) == 10
    assert abs(power(6, .4, .1) - .4 ** 6) < 1e-12
    assert abs(power(12, .5, 0) - sum(math.comb(12, k) for k in range(6, 13)) / 4096) < 1e-12
    assert abs(sum(binom(100, .2)) - 1) < 1e-12
    output = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(output, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
