# Evidence for PAPER.md

Every file here was generated from, or written against, the benchmark's private results repository at commit
`d531541`. The comparison arm is called `comparison` here and `bloat` in the kit's code.

| File | What it holds |
|---|---|
| `trials.csv` | One row per worker trial (76): run, project, pair, arm, date, model, CLI version, duration, turns, every token column, total tokens, peak context, number of outside references, void flag and reason, whether the trial is in a judged pair |
| `first_judge_pairs.csv` | One row per pair (38, of which 27 judged and 11 dropped for voids): the first judge's pick and confidence in each presentation order, the pair verdict, the must-pass checks each side failed in each order, judge tokens per call |
| `second_judge_pairs.csv` | The 18 close-call pairs re-judged by the second judge: its picks, confidences and must-pass failures per order, beside the first judge's verdict |
| `calibration.csv` | The 30 known-answer fixture pairs, both orders: expected preference and expected must-pass failures, then what the judge returned |
| `checks.md` | Every project's must-pass checks, rewritten in neutral words |
| `pair_notes.md` | Why each pair went the way it did, rewritten from the judges' reasons |
| `audits.md` | The 13 audits of the apparatus and runs: findings and what was done about them |

In the CSVs, "harness shown first" is the order the code calls `xy` and "comparison shown first" is `yx`.

What is not here, and why: the judges' verbatim reasons, the rubrics, the audit reports and any excerpt of a
submission. All of them quote the private projects (file names, records, people, places). The descriptions in
`checks.md`, `pair_notes.md` and `audits.md` replace them.
