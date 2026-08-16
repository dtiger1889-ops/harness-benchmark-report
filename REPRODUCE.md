# Reproducing the benchmark

This document is written for someone who has never seen this repo and has no
context beyond it. Everything needed to re-run all 154 trials — the runner, the
frozen prompts, the pass/fail verifiers, the harness templates, the seed data,
and the analyzer — ships in [`bench/`](bench/). Follow the steps in order.

The results reported in [REPORT.md](REPORT.md) came from exactly these files.

---

## 0. What you are actually running

Each **trial** is one headless Claude Code session, launched with `claude -p`
into a freshly materialized throwaway directory, given one frozen prompt, and
left alone. The runner then reads the session's own JSONL transcript for token
usage, runs a pass/fail verifier against the files Claude produced, appends one
row to `results.csv`, archives the transcript and the whole trial folder, and
deletes the live directory.

Each **pair** is two trials of the same task and trial number under the two
conditions:

- **H0 (control)** — bare directory. Task seed data only, no harness files.
- **H1 (treatment)** — identical seed data *plus* the `CLAUDE.md` /
  `CHECKPOINT.md` harness files. Which harness files depends on the task; see
  the table in [REPORT.md](REPORT.md) § The 8 tasks.

Only the harness files differ within a pair. Same prompt, same seeds, same
model, same tool permissions, same machine.

**Pairing order is `ABBAAB`** — the condition that runs first alternates every
pair (pair 1: H0 then H1; pair 2: H1 then H0; pair 3: H0 then H1; …). This is
the only defense against time-of-day and server-load drift, which on a run this
long is a real effect. Do not "simplify" it by running all H0 trials and then
all H1 trials — that silently confounds the whole experiment.

Analysis is a **paired Wilcoxon signed-rank test** per task per metric, over the
matched (H0, H1) differences.

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| Windows + PowerShell 5.1 or PowerShell 7 | The runner and verifiers are PowerShell. See § 7 for porting. |
| [Claude Code CLI](https://claude.com/claude-code) on `PATH` | `claude --version` must work from a plain shell. The version string is captured into every results row. |
| An Anthropic account with API/subscription access | 154 trials of real model calls. Budget accordingly. |
| Python 3.9+ on `PATH` | Used by the verifiers, the seed generator, and the analyzer. |
| Python packages | `pip install fpdf2 scipy numpy matplotlib` |

`fpdf2` generates the Task 2 seed PDFs. `scipy` + `numpy` run the statistics —
without them `analyze.py` degrades to descriptive stats only and prints a
warning. `matplotlib` is needed only for `--plot`.

---

## 2. Set up the bench

```powershell
git clone https://github.com/dtiger1889-ops/harness-benchmark-report.git
```

Everything below runs from the `bench` folder inside the clone:

```powershell
cd harness-benchmark-report\bench
```

The bench is location-independent — `run-trial.ps1` resolves every path from its
own folder (`$PSScriptRoot`), so it works wherever you cloned it.

Generate the Task 2 seed PDFs (they are generated rather than committed, so the
repo carries no binaries; generation is deterministic):

```powershell
cd templates\seeds\task2A; python generate_pdfs.py; cd ..\..\..
```

That writes three PDFs into `templates/seeds/task2A/` and mirrors them into
`templates/seeds/task2B/`.

### The permission file matters

`bench/.claude/settings.json` pre-approves `Bash`, `Read`, `Edit`, `Write`,
`Glob`, `Grep`. Headless `claude -p` cannot answer a permission prompt, so
without this every trial stalls and then trips the wall-time limit. It is
deliberately permissive because trials run in a throwaway directory that is
deleted after each run — do not copy this file into a real project.

---

## 3. Smoke-test before spending money

```powershell
.\dry-run.ps1
```

This runs one H0 and one H1 trial of Task 1A, parses both transcripts, runs the
verifier, and calls `analyze.py` on the resulting 2-row CSV.

**It passes if** both rows show non-zero token counts and `passed=1`, and
`analyze.py` completes without an exception. If token counts come back zero, the
transcript was not captured — check that `claude --version` works from a plain
shell and that you are not launching from inside an interactive Claude Code
session (see § 6).

Then delete the smoke-test rows before the real run, so they do not contaminate
the dataset:

```powershell
Remove-Item .\results.csv
```

---

## 4. Run the trials

Each launcher in `launchers/` runs the full 10-pair `ABBAAB` sequence for one
task. They call `.\run-trial.ps1` relative to the current directory, so run them
**from `bench/`**, not from inside `launchers/`:

```powershell
.\launchers\phase2-1B.ps1
```

Repeat for each task, in any order:

```
launchers\phase2-1B.ps1   launchers\phase2-2A.ps1   launchers\phase2-2B.ps1
launchers\phase2-3.ps1    launchers\phase2-4A.ps1   launchers\phase2-4B.ps1
launchers\phase2-4C.ps1
```

Task 1A was the pilot and ran at n=7 before the launcher pattern was settled;
to include it, run 7 pairs by hand in `ABBAAB` order:

```powershell
.\run-trial.ps1 -Task 1A -Condition H0 -TrialNum 1
```

```powershell
.\run-trial.ps1 -Task 1A -Condition H1 -TrialNum 1
```

…continuing with the first-condition alternating each pair.

**Budget:** roughly 3 hours of wall-clock across all tasks, plus the analysis
pass. Trials are sequential by design — running them in parallel would put them
in competition for the same rate limits and destroy the pairing.

Anything appended to `results.csv` is permanent to the dataset. To exercise the
runner without writing a row, use `-DryRun`:

```powershell
.\run-trial.ps1 -Task 4C -Condition H1 -TrialNum 1 -DryRun
```

---

## 5. Analyze

```powershell
python analyze.py
```

Reads `results.csv` from the bench folder and prints, per task: pair count,
success rates, and a per-metric table of H0 median, H1 median, percent
difference, Wilcoxon p-value, and significance stars.

To analyze the published dataset instead of your own run:

```powershell
python analyze.py --csv ..\results.csv
```

Add `--plot` for per-turn context-growth curves (writes PNGs to
`bench/results/`). Curves are re-parsed from the archived session JSONLs, so
`--plot` only produces output for trials whose folders still exist locally.

### The decision rule, stated in advance

> Reject H0 for a task if paired Wilcoxon p < 0.05 **and** H1 median tokens are
> lower **and** H1 success rate ≥ H0 success rate.

This was fixed before the data came in. Apply it as written; the interesting
outcome of this experiment was that it rejects in *both* directions depending on
the task.

### One metric needs care

`turn_count` counts usage-bearing rows in the SDK transcript, and the SDK emits
one row per **content block** — a response with text plus a tool call produces
two. It is not a count of decisions, and it is inflated by however much the model
narrates. `turn_logical` (distinct `message.id`) is the honest turn metric.

This mattered: the original analysis reported turn-count effects on Tasks 4A, 4B
and 4C that vanished under `turn_logical`. Token, cache-read, and input findings
were unaffected because those are direct API measurements. **Report
`turn_logical`.** `turn_count` is retained only so the correction stays auditable.

---

## 6. Things that will bite you

- **Do not launch trials from inside an interactive Claude Code session.** The
  CLI's anti-recursion guard blocks nested `claude -p`, and the safety
  classifier blocks the workaround. Use a plain PowerShell window.
- **Pin the model and stay off fast mode.** The runner defaults to
  `-Model claude-sonnet-4-6`. Fast mode substitutes a different model, which
  breaks comparability with the published rows. Every row records the model, so
  check the column afterwards.
- **Never let the harness leak into H0.** H0's whole meaning is "no harness in
  scope". Keep the bench out of any directory tree that contains a `CLAUDE.md`
  above it — a parent-directory harness file is invisible in the results and
  silently converts your control into a second treatment.
- **Pass long prompts via file or stdin, not as a positional argument.**
  PowerShell 5.1 truncates a long string at the first embedded double quote, and
  the failure mode is a silently empty output file rather than an error. The
  runner reads prompts from `prompts/*.txt` for this reason.
- **A trial that hits the wall-time limit still writes a row** with
  `passed=0`. Do not quietly drop it — an unbalanced pair breaks the paired
  test. Re-run that trial number under both conditions.
- **`results.csv` is append-only in practice.** There is no de-duplication: a
  re-run with the same task/condition/trial number adds a second row and the
  pairing logic will use whichever it encounters. Delete the bad rows by hand.

---

## 7. Adapting it

**Port to Mac/Linux.** The runner, verifiers and launchers are PowerShell; the
prompts, templates, seeds and analyzer are platform-neutral. Either install
PowerShell 7 or reimplement `run-trial.ps1` — it is ~230 lines and its contract
is simple: materialize a trial dir, run `claude -p`, parse the JSONL for
`usage`, run the verifier, append a row, archive, clean up.

**Test a different harness shape (H2, H3, …).**

1. Add `templates/H2-<name>/` mirroring `H1-base/` (top-level `CLAUDE.md` only)
   or `H1-task4C/` (top-level + per-sibling `CLAUDE.md` + `CHECKPOINT.md`). For
   a task-specific variant, name it `templates/H2-task<ID>/` and the runner
   picks it up automatically.
2. Add `'H2'` to the `[ValidateSet('H0','H1')]` on the `$Condition` parameter in
   `run-trial.ps1`, and extend the `$TemplateBase` branch just below it.
3. Copy a launcher and swap the condition, writing to a fresh CSV rather than
   `results.csv`.
4. **Compare H1 vs H2, not just H0 vs H2.** The question worth answering is
   whether the new variant beats the existing harness, not whether it beats
   nothing.

**Add a task.** A task needs three things: `prompts/task<ID>.txt` (frozen before
the first trial — editing a prompt mid-experiment invalidates every prior row),
`verifiers/task<ID>.ps1` (returns `$true`/`$false`), and either
`templates/seeds/task<ID>/` for shared seed data or dedicated
`templates/H0-task<ID>/` and `templates/H1-task<ID>/` folders. Then add the ID
to the `[ValidateSet]` on `$Task`.

Interpret any new result against the regimes in [REPORT.md](REPORT.md)
Findings 1–4 — trivial, structured, exploratory. A variant's effect is
characterized by *which regime it moves*, not by an aggregate number across
tasks that behave in opposite directions.

---

## 8. What this design cannot tell you

Carried from [REPORT.md](REPORT.md) § Known limitations, because they are
properties of this harness and will limit your rerun too:

- **Peak context is never stressed.** No task got near the context window, so
  nothing here tests whether a harness slows context growth. Testing it needs
  synthetic tasks an order of magnitude larger.
- **The harness files are frozen and accurate.** A *stale* `CLAUDE.md` is
  plausibly worse than no harness at all, and that is the realistic failure mode
  for a long-lived personal setup. Untested here.
- **Five siblings only.** Whether the payoff scales with project count is
  unknown.
- **One model, one machine, one operator.** No cross-environment claim.
- **Eight hand-chosen tasks.** Not a random sample of real agent work.

---

The pattern these trials measure is implemented in
[claude-harness-toolbox](https://github.com/dtiger1889-ops/claude-harness-toolbox).
