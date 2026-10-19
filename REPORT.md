# Does a CLAUDE.md + CHECKPOINT.md harness actually save tokens?

An empirical benchmark across 8 tasks, 154 paired Claude Code trials.

> **Output token correction (2026-10-18):** the 2026-10-17 recount took output tokens from per-message log rows, which hold only a partial count; each trial's final result record has the complete one (one trial: 340 vs 2,274). Output and cost below now use the complete count; cache, peak and turn figures did not change. Effects: one more loss (Task 2B, harness pre-built: cost +7%, output +41%), Task 1B's output gap falls from +146% to a non-significant +27%, and output turns out to be 10–26% of each trial's cost. Still no task got cheaper with the harness.
>
> **Token and cost correction (2026-10-17):** the first version of this report summed every assistant row in each trial's log. Claude Code writes one row per content block and repeats the whole message's token usage on each, so most API calls were counted two or three times: cache reads were overstated by a median 35% and cache writes by 48%. Recounted once per message and priced at API rates, **the harness made no task significantly cheaper.** The three "harness wins" (Tasks 3, 4A, 4C) are cost-neutral; the two losses (1B, 4B) hold; Task 1A becomes a small loss. The tables and findings below use the corrected numbers; the old figures appear only in marked "superseded" notes.
>
> The first version's headline, kept here because it was wrong (superseded, do not cite): *"It saves 20–45% of tokens on exploratory multi-project tasks, is roughly neutral on well-structured single-project tasks, and actively costs tokens (up to +136% output, +80% cache reads) on trivial or pre-oriented tasks."* Its "clearest win" was Task 4C (−45% output, −22% cache reads, −22% input). Both came from the double-counted rows.
>
> **Methods correction (2026-05-22):** the original analysis used the Claude Code SDK's `turn_count`, which counts *content blocks* (text + tool_use emitted separately) rather than logical decision turns. The 154 trials were backfilled with a `turn_logical` metric (distinct `message.id` count). The turn-count headlines for Tasks 4A, 4B, and 4C were SDK-counting artifacts. (That note originally said the token findings were unchanged; the 2026-10-17 correction above supersedes that.) What changed for the turn findings:
>
> | Task | Original `turn_count` | Corrected `turn_logical` |
> |---|---|---|
> | 4A | −19% turns, p=0.010 (reported as a significant win) | +25% turns, not significant |
> | 4B | +56% turns, p=0.002 (reported as the clearest loss) | 0% turns, not significant |
> | 4C | −25% turns, p=0.008 (reported as the clearest win) | 0% turns, not significant |
>
> Both counts are in [`results.csv`](results.csv): `turn_count` keeps the original numbers, `turn_logical` holds the corrected ones. Current two-sided turn p-values are listed under the Results table.

---

## TL;DR

A persistent two-file harness (`CLAUDE.md` for stable rules, `CHECKPOINT.md` for mutable state) does not save money in a single fresh session at these task sizes. It **costs 14–31% more** when the task is trivial or the prompt already tells Claude where to look, +7% on one task where the harness was pre-built, and is **roughly cost-neutral** (−5% to +6%, not significant) everywhere else, including the multi-project exploration tasks it was designed for.

**Token wins, none that lowers cost:** Task 3 (complete a half-finished script) — 13% fewer cache reads and 17% fewer decision turns, paired Wilcoxon p ≤ 0.01. Its 12% extra cache writes cancel the saving in dollars (cost −5%, p = 0.16). Task 1A writes 10% less output (p = 0.016) but still costs 4% more from extra cache tokens.

**Clearest loss:** any task where the prompt itself specifies the path — the harness startup ritual runs and adds pure overhead. On a "session is scoped to one folder; ask for parent access" task, H1 cost +14% (p = 0.006), mostly from +34% cache writes, at the same number of decision turns.

**What this doesn't test:** the harness exists to let a later session resume work. Every trial here was one fresh session, so the resume payoff is unmeasured. Peak context never got close to the 200K window either, so "the harness slows context-window growth" is **untested**, not supported.

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
- **Analysis:** paired Wilcoxon signed-rank test per task per metric (two-sided).
- **n:** 10 pairs per task (7 for the initial pilot task). 154 trials total.
- **Metrics captured per trial:** `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_create_tokens` (each counted once per API message since the 2026-10-17 correction), `peak_context` (max prompt-side total of any one call), `turn_count` (raw content-block count from the SDK jsonl), `turn_logical` (distinct `message.id`, added 2026-05-22 — see Methods correction at top), `duration_s`, `passed`, `compaction_events`, and **cost** (API-equivalent dollars at Sonnet 4.6 rates; every cache write was a 1-hour write, so the price is exact).

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

Deltas are `(H1 median − H0 median) / H0 median`, tokens counted once per message (corrected 2026-10-17). Two-sided paired Wilcoxon p in parentheses; bold is p < 0.05. Uncached input is left out: it is single-digit tokens per trial in both arms.

| Task | n | Δ cost | Δ cache_read | Δ cache_create | Δ output | Δ peak | Δ turns | Read |
|---|---|---|---|---|---|---|---|---|
| 1A | 7 | **+3.9%** (0.016) | **+4.0%** (0.016) | **+4.8%** (0.016) | **−10.0%** (0.016) | **+3.7%** (0.016) | 0% | Small loss; about $0.002 per trial; less output. |
| 1B | 10 | **+31.4%** (0.010) | **+75.4%** (0.027) | **+21.4%** (0.002) | +26.7% (0.11) | **+6.1%** (0.002) | +67% (0.063) | Harness tax on trivial parent-scoped work. |
| 2A | 10 | +4.1% (0.28) | +2.6% (0.16) | +5.4% (0.065) | +4.1% (0.85) | **+3.4%** (0.004) | 0% | Neutral. |
| 2B | 10 | **+7.2%** (0.020) | +1.7% (0.77) | +4.2% (0.065) | **+41.3%** (0.002) | +0.1% (0.19) | 0% | **Harness costs more** with the harness pre-built; mostly extra output. |
| 3 | 10 | −5.1% (0.16) | **−13.1%** (0.010) | +12.0% (0.56) | +1.3% (0.85) | **+7.0%** (0.002) | **−17%** | Fewer reads and turns; extra writes cancel it in dollars. |
| 4A | 10 | +6.0% (0.56) | +28.9% (0.19) | −2.9% (1.0) | −3.5% (0.56) | +0.6% (0.70) | +25% | Neutral. |
| 4B | 10 | **+13.6%** (0.006) | +8.4% (0.32) | **+33.6%** (0.006) | −1.5% (0.77) | **+10.4%** (0.002) | 0% | **Harness costs more** when the prompt pre-orients; mostly cache writes. |
| 4C | 10 | +3.6% (0.63) | +8.0% (1.0) | +5.2% (0.38) | −3.9% (0.56) | +2.3% (0.23) | 0% | Neutral. Full hierarchical harness. |

Output and cost use each trial's complete output count (restated 2026-10-18). Median cost per trial: $0.06–$0.14. Turn p-values (two-sided): 1B 0.063, 3 0.008, 4A 0.21, 4B 1.0, 4C 0.78. Peak context: H1 adds 0–10%; none approached compaction.

> **Superseded figures (first version, every-row sums; do not cite):** Δ output / Δ cache_read / Δ input — 1A −9.6% / +3.2% / +0.0%; 1B +136% / +80% / +67%; 2A −5% / +7% / +3%; 2B −14% / +7% / +3%; 3 +63% / −9% / −9%; 4A −25% / −18% / −19%; 4B +35% / +64% / +55%; 4C −45% / −25% / −25%.

**Where the numbers live in [`results.csv`](results.csv):** the original columns `total_input`, `total_output`, `cache_read` and `cache_create` are the first version's every-row sums, kept unchanged as the record of the error; `turn_count` is the original content-block count. The corrected values are the six columns at the end: `dedup_input`, `dedup_cache_read` and `dedup_cache_create` (counted once per message), `final_output` (the complete output count from each trial's final result record), `dedup_messages` (distinct message ids: equal to `turn_logical` wherever that column is filled, and filled for every trial, including 1A and 2A), and `cost_usd`. The table above recomputes from those columns. `peak_context` was never affected: a per-call maximum is not inflated by repeated rows.

---

## Findings

### 1. The harness costs extra when the prompt already orients Claude; it doesn't pay for itself elsewhere

- **Trivial or pre-oriented tasks (1B, 4B):** harness is pure overhead. Claude runs the startup ritual — look for `CHECKPOINT.md`, read `CLAUDE.md`, confirm the next step — finds no useful state, and pays for it. 1B is the degenerate case: no state exists at all, and the harness adds +75% cache reads and +31% cost, and ~67% more decision turns (p = 0.063, not significant). 4B is the more interesting one: the prompt itself tells Claude *"Request access to the parent directory if you need it."* That's all the orientation required. H1's harness work on top costs +34% cache writes and +14% overall, at the same number of decision turns.

- **Structured single-project tasks (1A, 2A, 2B, 3):** near-neutral, except that with the harness pre-built (2B) Claude writes 41% more output and costs 7% more; why was not inspected. Task 3 shows the largest token saving (−17% turns, −13% cache reads), but its extra cache writes leave cost flat.

- **Exploratory multi-project tasks (4A, 4C):** cost-neutral (+6%, +4%, not significant), with no significant token difference. The first version of this report called these 20–45% savings and said this was "where the harness earns its keep"; that came from the double-counted rows.

### 2. Per-sibling `CLAUDE.md` cuts reading and turns, not cost

The 4A vs 4C cross-comparison (same prompt, same data, only H1 template differs). Unpaired medians, no significance test; the two tasks ran at different times.

| Metric (H1 medians) | H1-4A (top-level only) | H1-4C (full hierarchy) | Change |
|---|---|---|---|
| Turns (logical) | 10 | 8 | −20% |
| Output tokens | 2,256 | 2,228 | −1.2% |
| Cache reads | 169,232 | 143,479 | −15% |
| Cache writes | 9,888 | 10,914 | +10% |
| Cost per trial | $0.141 | $0.145 | +2.8% |

Per-sibling `CLAUDE.md` lets Claude classify a folder as relevant or irrelevant without opening the full README, so it reads less and decides in fewer turns. The extra files are cache writes, which cost 20× a read, so the cost comes out even.

Verdict: **full hierarchy orients with less reading than top-level-only; neither is cheaper than no harness on this task.**

> Superseded (every-row sums): output 467 → 364, cache_read 209,638 → 192,592, input 14.5 → 13.5, with the verdict "full hierarchy > top-level-only > no harness." Superseded 2026-10-18 (partial output counts): output 401 → 290, cost $0.111 → $0.113.

### 3. The "peak context" claim is untested, not refuted

The original hypothesis had a subcomponent: "harness slows context-window growth." None of the 8 tasks actually approached compaction. Peak context across the entire 154-trial dataset topped out around 22K tokens (Task 2B), roughly 11% of the 200K window. The harness can't relieve pressure that doesn't exist; if anything it raises peak slightly (+3% to +10% in five tasks), because its own files sit in context.

This is a real gap in the experiment. Task 4 was originally designed to consume >150K tokens, but 5 small siblings don't stress sonnet-4-6 that hard. Testing the peak-context claim properly would require synthetic tasks designed to hit ~150K+ (order-of-magnitude more data per sibling, or many more siblings).

For any task whose peak stays comfortably below 200K — i.e. most real work — this benchmark has nothing to say about whether the harness helps with compaction. Don't sell the pattern on that basis.

### 4. There is no consistent output-token tax

With complete output counts, output differs significantly in only two tasks, in opposite directions: with the harness pre-built (2B) H1 writes 41% more (p = 0.002), and on Task 1A it writes 10% less (p = 0.016). Task 1B's +27% is not significant (p = 0.11); the earlier "+146% output tax on 1B" came from partial per-message counts. Tasks 3, 4A, 4B and 4C are within ±4%. Output is 10–26% of the bill here (about 500–2,300 tokens per trial); cache reads and writes are the rest.

> Superseded (first version): "The output-token tax is real, and it's task-shaped" — present on closed tasks (1B +136%, 3 +63%, 4B +35%), inverted on exploratory tasks (4A −25%, 4C −45%), explained as narration the harness prevented. Those figures were an artifact of the double counting, so the explanation built on them does not stand either.

### 5. Wall-clock and tokens are different axes

Duration didn't track tokens: H1 took about +7% longer on 4A and +12% on 4C. With the corrected numbers the harness isn't cheaper on those tasks either, so on single-session exploration at this size it costs a little time and saves no money.

> Superseded (first version): "If you care about API cost, it's a clear win on exploratory work."

### 6. 100% success rate across every task, every condition

Both H0 and H1 passed the verifier in every trial of every task. The success-rate component of the original hypothesis is trivially tied. On tasks this size the harness changed neither correctness nor, on exploratory work, cost.

---

## Verdict on the hypothesis

**Original pre-registered rule:** reject H0 for a task if paired Wilcoxon p < 0.05, H1 median tokens are lower, and H1 success rate ≥ H0 success rate.

Applying that rule per task to the corrected token counts and to cost:

- 1A: reject H1 on cost, cache reads and cache writes (+4–5%, p = 0.016); negligible in dollars. Output is lower with the harness (−10%, p = 0.016).
- 1B: reject H1 (cost +31%, cache reads +75%, cache writes +21%, all p < 0.05; output +27%, p = 0.11, and turns +67%, p = 0.063, not significant).
- 2B: reject H1 on cost (+7%, p = 0.020) and output (+41%, p = 0.002).
- 2A, 4A, 4C: no rejection either way.
- 3: reject H0 on cache reads only (−13%, p = 0.010; turns −17%); cost −5%, p = 0.16 (not significant).
- 4B: reject H1 on cost (+14%) and cache writes (+34%), both p = 0.006.

> Superseded (first version): 4A and 4C "reject H0 on tokens" (output −25%/−45%, cache_read −18%/−22%, input −19%/−22%); 4B "reject H1 on cache_read and input" (+64%/+55%). The first version called the hypothesis "conditionally true" on exploratory work: "A harness reduces token spend on tasks where orientation … is a meaningful fraction of the work."

The hypothesis as originally written — "a good harness reduces tokens and slows context growth, making sessions cheaper/faster/more successful" — is **not supported** in a single session at this scale. What the data does support:

> A harness adds measurable cost when the prompt already specifies the path or the task is trivial, and is roughly cost-neutral otherwise. Whatever it's worth has to come from resuming work across sessions, which this benchmark didn't measure.

---

## Recommendations if you're considering the pattern

1. **Don't add a harness to a single small project.** It's ceremony Claude has to pay for. 1A/2A/2B show no benefit (2B costs 7% more); 1B/4B show 14–31% higher cost.

2. **Don't expect a harness to save tokens in one session, even on multi-project work.** 4A/4C were cost-neutral. If you use one, it's for resuming work across sessions — test that on your own work before relying on it.

3. **If you have a harness, hierarchy helps orientation but not the bill.** Per-project `CLAUDE.md` cut reads by 15% and turns by 20% versus top-level-only, at the same cost.

4. **Keep `CLAUDE.md` short (~15–30 lines).** Every harness token is a cache write, and writes cost 20× a read. The 4B loss is mostly cache writes.

5. **Don't sell the pattern on "it prevents context-window saturation."** At task sizes where that matters, this experiment has no data. At task sizes this experiment covers, peak context is never the bottleneck.

6. **Don't promise faster or cheaper single sessions.** Neither showed up here.

> Superseded recommendations (first version): "Do add a harness to a multi-project directory … the wins are large (20–45%) and consistent" and "Don't promise faster sessions. Promise cheaper ones, on the right shape of work." Both rested on the double-counted rows.

---

## Known limitations

- **One session per trial:** the harness's stated purpose — resuming work in a later session — is not exercised.
- **Sibling count:** only tested with 5. Scaling unknown.
- **Stale harness:** H1 files were frozen and accurate across the experiment. A wrong or outdated `CLAUDE.md` is probably *worse* than no harness, and this is the real risk case for long-running personal setups — untested here.
- **Model:** sonnet-4-6 only. Smaller/larger models may allocate exploration budget differently.
- **Task distribution:** 8 tasks, hand-chosen. Not a random sample of real Claude Code work.
- **Single machine, single operator.** No cross-environment generalization claim.
- **Peak context:** never stressed. The hypothesis subcomponent about context growth is not tested.
- **Warm cache:** trials ran back to back, so each trial's shared system prompt was usually already cached. That prefix is identical in both arms (about $0.003 per trial), so it shouldn't favor either.

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

**The shipped runner still has the counting error.** `bench/run-trial.ps1` sums every usage row of the session log into `total_input`, `total_output`, `cache_read` and `cache_create`, and `bench/analyze.py` tests those columns, so a rerun as shipped reproduces the superseded figures. If you sum token usage from Claude Code session logs yourself: count each `message.id` once (Claude Code writes a separate log row for each content block of a message — text, each tool call — and copies the message's full usage onto every one of them), take output from the session's final result record, and price cache writes and cache reads separately.

Not shipped: the per-trial session JSONLs and full trial folders (`sessions-archive/`, `trials-archive/` in the original bench). They were retained for per-turn curve re-parsing and anomaly inspection, and they are what made the 2026-10-17 recount possible; `results.csv` carries every metric the report uses.

Total wall-clock to rerun end-to-end: roughly 3 hours of active trial time plus the analysis pass. If you want to adapt this to a different harness shape or a different task distribution, the runner and analyzer are the only pieces that need to stay; everything else is data. [REPRODUCE.md](REPRODUCE.md) § 7 walks through adding an H2 variant or a new task.
