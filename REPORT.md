# Does a CLAUDE.md + CHECKPOINT.md harness actually save tokens?

An empirical benchmark across 8 tasks, 154 paired Claude Code trials.

> **Methods correction (2026-05-22):** the original analysis used the Claude Code SDK's `turn_count`, which counts *content blocks* (text + tool_use emitted separately) rather than logical decision turns. The 154 historical trials were backfilled with a corrected `turn_logical` metric (distinct `message.id` count). The turn-count headlines for Tasks 4A, 4B, and 4C turned out to be SDK-counting artifacts — those three tasks show no significant difference in actual decision turns. **The token, cache_read, and input findings are unchanged** (those are direct API measurements, not turn-derived) and the qualitative conclusions still hold: harness helps on exploratory work, hurts on pre-oriented work. The tables and numbers below have been updated. See [turn_logical_schema_bump.md](turn_logical_schema_bump.md) for full details.

---

## TL;DR

A persistent two-file harness (`CLAUDE.md` for stable rules, `CHECKPOINT.md` for mutable state) is not uniformly good. It saves 20–45% of *tokens* on exploratory multi-project tasks, is roughly neutral on well-structured single-project tasks, and actively *costs* tokens (up to +136% output, +80% cache reads) on trivial or pre-oriented tasks. The effect tracks one variable: whether orientation — figuring out which files or folders to read — is the task's actual bottleneck.

**Clearest win:** full hierarchical harness (top-level `CLAUDE.md` + per-sibling `CLAUDE.md` + `CHECKPOINT.md` in every sibling folder) on a 5-sibling classify-and-combine task — −45% output tokens, −22% cache reads, −22% input tokens, paired Wilcoxon p ≤ 0.05 on all of them. (Decision-turn count was statistically unchanged; the savings came from less narration and fewer exploratory reads per turn, not fewer turns overall.)

**Clearest loss:** any task where the prompt itself specifies the path — the harness startup ritual runs and adds pure overhead. On a "session is scoped to one folder; ask for parent access" task, H1 used +64% cache reads and +55% input tokens at p = 0.002. (Decision-turn count was unchanged; the harness wasn't taking more turns, it was emitting more narration per turn.)

Peak context was never meaningfully affected because none of the tasks got close to the 200K window. The "harness slows context-window growth" claim is effectively **untested**, not supported.

---

## What was tested

### The harness pattern

Over time I'd built up a convention for my personal Claude Code work:

- **Top-level `CLAUDE.md`** at the root of a projects folder — stable rules, startup sequence, list of projects, pointers.
- **Per-project `CLAUDE.md`** (~15–30 lines) — what this project is, how to run it, gotchas.
- **Per-project `CHECKPOINT.md`** — mutable state: current status, open threads, next step, key decisions. Overwritten in place, not appended.
- **`SessionStart` hook** that prints `CHECKPOINT.md` when a session opens.

The explicit goal of this pattern is to make sessions cheaper and more resumable: Claude reads a compressed project state on launch instead of re-deriving it from the filesystem each time.

The question was whether that pattern actually pays off in tokens, or whether it's ornamental infrastructure that *feels* like it should help.

### Experimental design

- **H0 (control):** bare trial directory, no harness files, task seeds only.
- **H1 (treatment):** same seeds plus one or more `CLAUDE.md`/`CHECKPOINT.md` files (varies by task — see below).
- **Model pinned:** `claude-sonnet-4-6` across all 154 trials.
- **Runner:** invokes `claude -p "<prompt>" --output-format stream-json --no-session-persistence` with pre-approved tools (no permission prompts), captures JSONL, runs a PowerShell verifier, appends a results row, archives JSONL + full trial folder, then deletes the live trial dir.
- **Pairing:** `ABBAAB` alternating sequence per task (H0-0, H1-0, H1-1, H0-1, H0-2, H1-2, …) to control for time-of-day and server-load effects.
- **Analysis:** paired Wilcoxon signed-rank test per task per metric.
- **n:** 10 pairs per task (7 for the initial pilot task). 154 trials total.
- **Metrics captured per trial:** `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens`, `peak_context` (max prompt-side total across turns), `turn_count` (raw content-block count from the SDK jsonl), `turn_logical` (distinct `message.id`, added 2026-05-22 — see Methods correction at top), `duration_s`, `passed`, `compaction_events`.

### The 8 tasks

| # | Task | H1 harness |
|---|---|---|
| 1A | Write a non-trivial Python script. Scoped to empty project dir. | Top-level `CLAUDE.md` only. |
| 1B | Same as 1A but access scoped to a *parent* dir containing the empty project. | Top-level `CLAUDE.md` at parent. |
| 2A | Extract data from 3 PDFs into a CSV template. | Top-level `CLAUDE.md` only. |
| 2B | Same seeds as 2A, but H1 ships with the full harness *pre-built* (pointers only, no answers). | Top-level + per-project `CLAUDE.md` + empty `CHECKPOINT.md`. |
| 3 | Complete a half-finished Python script (seeded identically both conditions). | Top-level `CLAUDE.md`. |
| 4A | 5 sibling folders (3 irrelevant, 2 relevant with CSV data). Classify, combine, emit `report.py`. | **Hybrid:** top-level `CLAUDE.md` only; siblings keep plain `README.txt`/`notes.txt`/`config.txt`. |
| 4B | Same 5-sibling structure, but session starts scoped to *one* sibling; prompt says "request access to the parent if you need it." | Full hierarchical (top-level + every sibling has `CLAUDE.md`). |
| 4C | Same prompt and data as 4A, but with full hierarchical harness. Added after 4A to isolate per-sibling harness value. | **Full:** top-level `CLAUDE.md` + per-sibling `CLAUDE.md` + `CHECKPOINT.md` in each of the 5 siblings. |

4C is the crucial addition. Task 4A as originally designed was a "hybrid" harness (top-level only + plain siblings). The `Projects/` convention I'm actually running in practice has per-sibling harness files too. Without 4C, the benchmark couldn't tell me whether the hybrid was the efficient sweet spot or whether the full hierarchy adds real value on top.

All tasks used `claude -p` headless mode (no interactive clarification) with a pass/fail verifier. Success rate was 100% across all 154 trials — this experiment does not measure success rate, it measures efficiency.

---

## Results

Deltas are `(H1 median − H0 median) / H0 median`. `Δ turns` uses the corrected `turn_logical` metric (2026-05-22 backfill — see Methods correction at top). Bold cells are p < 0.05 on the listed metric.

| Task | n | Δ turns | Δ output | Δ cache_read | Δ input | Δ peak | p (turns) | Read |
|---|---|---|---|---|---|---|---|---|
| 1A | 7 | n/a* | −9.6% | +3.2% | +0.0% | +3.7% | n/a | Too trivial to show an effect. *Pilot pre-archive; no jsonl. |
| **1B** | 10 | **+67%** | **+136%** | **+80%** | **+67%** | +6% | 0.004 | Harness tax on trivial parent-scoped work. |
| 2A | 10 | n/a* | −5% | +7% | +3% | +3% | n/a | Neutral. *Pilot pre-archive; no jsonl. |
| 2B | 10 | +0% | −14% | +7% | +3% | +0% | 0.75 | Neutral even with harness pre-built. |
| **3** | 10 | **−17%** | +63% | **−9%** | **−9%** | +7% | 0.004 | First real read-side win; output tax. |
| 4A | 10 | +25% | **−25%** | **−18%** | **−19%** | +1% | 0.93 | Top-level harness pays off on **tokens** — turn count unchanged. |
| 4B | 10 | +0% | +35% | **+64%** | **+55%** | +10% | 0.57 | **Harness hurts on tokens** when prompt pre-orients; turn count unchanged. |
| 4C | 10 | +0% | **−45%** | **−25%** | **−25%** | +2% | 0.39 | **Strongest H1 win on tokens.** Full hierarchical harness; turn count unchanged. |

Peak context: range −0% to +10% across all 8 tasks. None approached compaction.

---

## Findings

### 1. The harness payoff tracks "is orientation the bottleneck?"

Three regimes show up cleanly:

- **Trivial or pre-oriented tasks (1B, 4B):** harness is pure overhead. Claude runs the startup ritual — look for `CHECKPOINT.md`, read `CLAUDE.md`, confirm the next step — finds no useful state, and burns tokens narrating the ritual. 1B is the degenerate case (no state exists at all; harness adds ~67% more decision turns AND +136% output tokens). 4B is the more interesting one: the prompt itself tells Claude *"Request access to the parent directory if you need it."* That's all the orientation required. H1 doing harness work on top of an already-oriented prompt is strictly wasted motion — same number of actual decision turns (0% delta) but +45% more output tokens and +64% more cache reads spent on the ritual.

- **Structured single-project tasks (1A, 2A, 2B, 3):** near-neutral on reads. Task 3 shows a small real effect (−17% turns, −9% input). The harness keeps Claude on-task but there isn't enough surface area for it to compound.

- **Exploratory multi-project tasks (4A, 4C):** this is where the harness earns its keep — but the win is in tokens, not turns. 4A saved ~20% on every read-side metric; 4C saved ~25–45% and beat 4A's numbers across the board. Decision-turn count was statistically unchanged on both tasks; the savings came from less narration and fewer exploratory reads per turn.

### 2. Per-sibling `CLAUDE.md` adds measurable value beyond top-level-only

The 4A vs 4C cross-comparison (same prompt, same data, only H1 template differs) is the cleanest internal test in the dataset:

| Metric | H1-4A (top-level only) | H1-4C (full hierarchy) | Improvement |
|---|---|---|---|
| Median turns (logical) | 10 | 8 | −20% |
| Median output tokens | 467 | 364 | −22% |
| Median cache_read tokens | 209,638 | 192,592 | −8% |
| Median input tokens | 14.5 | 13.5 | −7% |

Per-sibling `CLAUDE.md` lets Claude classify a folder as relevant or irrelevant without opening the full README. Those avoided reads compound into less exploratory output chatter and lower cache pressure.

Verdict: **full hierarchy > top-level-only > no harness** on exploratory multi-project work.

### 3. The "peak context" claim is untested, not refuted

The original hypothesis had a subcomponent: "harness slows context-window growth." None of the 8 tasks actually approached compaction. Peak context across the entire 154-trial dataset topped out around 22K tokens (Task 2B), roughly 11% of the 200K window. The harness can't relieve pressure that doesn't exist.

This is a real gap in the experiment. Task 4 was originally designed to consume >150K tokens, but 5 small siblings don't stress sonnet-4-6 that hard. Testing the peak-context claim properly would require synthetic tasks designed to hit ~150K+ (order-of-magnitude more data per sibling, or many more siblings).

For any task whose peak stays comfortably below 200K — i.e. most real work — this benchmark has nothing to say about whether the harness helps with compaction. Don't sell the pattern on that basis.

### 4. The output-token tax is real, and it's task-shaped

On closed or pre-oriented tasks (1B +136%, 3 +63%, 4B +35%), H1 spends more *output* tokens than H0. Inspecting JSONLs, the extra output is protocol compliance: *"Let me check CHECKPOINT.md," "Next step per the harness is…,"* etc. This is the harness doing what it's designed to do — announcing orientation — at real token cost.

On exploratory tasks (4A −25%, 4C −45%), the tax inverts. Claude doesn't narrate *"let me check this sibling, let me check that sibling"* because `CLAUDE.md` already said which were relevant. The saved exploration chatter dwarfs the protocol compliance overhead.

Rule of thumb: small output tax on well-scoped work; output savings on exploration-heavy work. "The harness is always cheaper in output" is false.

### 5. Wall-clock and tokens are different axes

Duration didn't track token savings:

- Task 4A: −25% output tokens, +7% duration.
- Task 4C: −45% output tokens, +12% duration.

Reading `CLAUDE.md` adds latency even when it saves downstream work. If you care about developer wait time, the harness is a wash. If you care about API cost, it's a clear win on exploratory work. Don't conflate them when pitching the pattern.

### 6. 100% success rate across every task, every condition

Both H0 and H1 passed the verifier in every trial of every task. The harness reduces the *cost* of getting to correct, not the correctness itself, on tasks this size. The success-rate component of the original hypothesis is trivially tied — all evidence is in token metrics.

---

## Verdict on the hypothesis

**Original pre-registered rule:** reject H0 for a task if paired Wilcoxon p < 0.05, H1 median tokens are lower, and H1 success rate ≥ H0 success rate.

Applying that rule per task (turn-count tests use `turn_logical`, 2026-05-22 backfill):

- 1B: reject H1 (H1 worse on output, input, cache_read, and turns — turn_logical +67%, p=0.004).
- 1A, 2A, 2B: no rejection either way.
- 3: reject H0 on input, cache_read, and turns (turn_logical −17%, p=0.004).
- 4A: reject H0 on tokens (output −25%, cache_read −18%, input −19%, all p<0.05). Turn-count effect insignificant (+25%, p=0.93).
- 4B: reject H1 on cache_read and input. Output trended +35% but p=0.16 (NS). Turn-count effect insignificant (0%, p=0.57).
- 4C: reject H0 on tokens (output −45%, cache_read −22%, input −22%, all p≤0.05). Turn-count effect insignificant (0%, p=0.39).

The hypothesis as originally written — "a good harness reduces tokens and slows context growth, making sessions cheaper/faster/more successful" — is **globally false.** Some tasks favor H0 by a wide margin. It is **conditionally true** in a well-defined regime, which the data defines:

> A harness reduces token spend on tasks where orientation (identifying which files or folders to read) is a meaningful fraction of the work. On tasks where the prompt itself specifies the path, or where the task is too small for orientation to matter, the harness is neutral to harmful.

---

## Recommendations if you're considering the pattern

1. **Don't add a harness to a single small project.** It's ceremony Claude has to pay for. The 1A/2A/2B results show you'll see no benefit; the 1B/4B results show you can actively lose 40-130% more output tokens and 60-80% more cache reads.

2. **Do add a harness to a multi-project directory where sessions routinely start by Claude figuring out which project matters.** This is the 4A/4C regime and the wins are large (20–45%) and consistent.

3. **If you're going to have a harness, make it hierarchical.** Top-level-only is a worse Pareto point than top-level + per-project. The 4A vs 4C comparison pays the hierarchy's cost on output tokens and still wins on every read metric.

4. **Keep `CLAUDE.md` short (~15–30 lines).** H1 wins come from orientation, not content volume. A long `CLAUDE.md` reintroduces the output-tax overhead without adding orientation value.

5. **Don't sell the pattern on "it prevents context-window saturation."** At task sizes where that matters, this experiment has no data. At task sizes this experiment covers, peak context is never the bottleneck.

6. **Don't promise faster sessions.** Promise cheaper ones, on the right shape of work. The latency and tokens axes decoupled on every exploration task.

---

## Known limitations

- **Sibling count:** only tested with 5. Scaling unknown.
- **Stale harness:** H1 files were frozen and accurate across the experiment. A wrong or outdated `CLAUDE.md` is probably *worse* than no harness, and this is the real risk case for long-running personal setups — untested here.
- **Model:** sonnet-4-6 only. Smaller/larger models may allocate exploration budget differently.
- **Task distribution:** 8 tasks, hand-chosen. Not a random sample of real Claude Code work.
- **Single machine, single operator.** No cross-environment generalization claim.
- **Peak context:** never stressed. The hypothesis subcomponent about context growth is not tested.

---

## Reproducing this

**Full step-by-step instructions: [REPRODUCE.md](REPRODUCE.md).** The complete
benchmark infrastructure ships in [`bench/`](bench/) — these results came from
exactly those files:

- `bench/run-trial.ps1` — trial runner (copies template → invokes claude → captures JSONL → verifier → archive → CSV row).
- `bench/analyze.py` — paired Wilcoxon across all tasks.
- `bench/prompts/task{1A,1B,2A,2B,3,4A,4B,4C}.txt` — one canonical prompt per task, frozen before the first trial.
- `bench/verifiers/task{…}.ps1` — PowerShell pass/fail scripts.
- `bench/templates/H0-empty/`, `H1-base/`, `H1-task4C/`, `seeds/task{…}/` — golden copies, immutable during the experiment.
- `bench/launchers/phase2-{1B,2A,2B,3,4A,4B,4C}.ps1` — per-task runner scripts wrapping the 10-pair ABBAAB sequence.
- `bench/dry-run.ps1` — end-to-end smoke test; run it before spending money on a full sweep.
- `bench/.claude/settings.json` — the pre-approved tool list. Headless `claude -p` can't answer a permission prompt, so without this every trial stalls to the wall-time limit.
- [`results.csv`](results.csv) — one row per trial, 154 rows, at the repo root.

Not shipped: the per-trial session JSONLs and full trial folders (`sessions-archive/`, `trials-archive/` in the original bench). They were retained locally for per-turn curve re-parsing and anomaly inspection; `results.csv` carries every metric the report uses.

Total wall-clock to rerun end-to-end: roughly 3 hours of active trial time plus the analysis pass. If you want to adapt this to a different harness shape or a different task distribution, the runner and analyzer are the only pieces that need to stay; everything else is data. [REPRODUCE.md](REPRODUCE.md) § 7 walks through adding an H2 variant or a new task.
