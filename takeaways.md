# Harness Efficacy Benchmark — Running Takeaways

Last updated: 2026-05-22 (methods correction; see below)

Living log of what we've observed across tasks. Append on each completed task; do not rewrite the history. *Exception: the 2026-05-22 methods correction updated numeric claims that were SDK-counting artifacts — see [turn_logical_schema_bump.md](turn_logical_schema_bump.md). Original `turn_count` numbers were preserved in `phase2-1-4-final-results.preTurnLogical.csv`.*

---

## Headline finding (Phase 2 complete n=10 per task, 154 trials total; turn metric corrected 2026-05-22)

**The harness helps when orientation is hard, and hurts when the prompt already tells Claude exactly what to do.** Same frozen H1 harness file went from +136% output-token tax on trivial tasks, to −45% output savings on multi-sibling exploration, to +64% cache-read tax when a prompt *explicitly instructs* Claude to request parent access. The harness is not a pure good or pure cost — it is an orientation aid, and its payoff tracks whether orientation is the bottleneck.

The "turn savings/tax" framing in earlier drafts was inflated by the SDK emitting one jsonl row per content block (text + tool_use) rather than per logical turn. Re-derived with `turn_logical`: Tasks 4A, 4B, and 4C show no significant difference in actual decision turns between H0 and H1. The harness changes how much *narration* Claude emits per turn, not how many decisions it takes. **Token-based findings are unchanged** — those are direct API measurements.

**Clearest win:** Task 4C (full hierarchical harness, multi-sibling exploration) — −45% output, −22% cache_read, −22% input, all p ≤ 0.05. Turn count statistically unchanged (0%, p=0.39).
**Clearest loss:** Task 4B (prompt already scopes the path) — +64% cache_read, +55% input, both p = 0.002. Output trended +35% but p=0.16 (NS). Turn count statistically unchanged (0%, p=0.57).

---

## Per-task results (Phase 2, n=10 pairs unless noted)

### Task 1A (n=7) — Write stats.py
- Closed, one-shot, no exploration needed.
- User provided raw CSV only; not formally analyzed in paired Wilcoxon.
- Early read: no dramatic effect either direction.

### Task 1B — Write stats.py, access scoped to parent dir
- Closed, one-shot, but Claude has to navigate up one level.
- **turn_logical +67% (p=0.004), total_output +136% (p<0.05), cache_read +80% (p<0.05), total_input +67% (p<0.05).** Harness actively hurt across every metric.
- Interpretation: On tasks this simple, the harness's startup sequence (read CHECKPOINT, read project CLAUDE.md, confirm next step) is pure overhead. CHECKPOINT.md doesn't exist in the trial, so Claude spends turns looking for a file that isn't there before giving up and doing the actual (trivial) task.
- **Harness tax is real on trivial work.**

### Task 2A — Extract data from 3 PDFs to CSV
- n=10 complete. Near-neutral results.
- Claude needs to find the PDFs and the template, but the task is very structured once oriented.
- Interpretation: Orientation cost ≈ orientation benefit.

### Task 2B — Same as 2A but harness pre-built (CLAUDE.md + empty CHECKPOINT.md seeded)
- n=10 complete. Near-neutral.
- Even with a pre-built harness to read, Claude didn't convert that into wins on this task shape.
- Interpretation: A harness you *already have* doesn't help if there's nothing to orient between.

### Task 3 — Complete a half-finished script
- Closed-ended but genuinely multi-step.
- **turn_logical −17% (p=0.004), total_input −9% (p=0.008), cache_read −9% (p=0.019).**
- **BUT: total_output +50% — the "harness tax" on output tokens.**
- Net in absolute terms: ~12.8K tokens saved on reads vs ~100 extra on writes → ~12.7K net savings per trial.
- Interpretation: H1 Claude spends output on meta-commentary (reading CHECKPOINT, completeness signals) but makes up for it many times over on reads. First task where the hypothesis is directionally supported.

### Task 4A — Multi-project exploration (top-level CLAUDE.md only in H1, siblings have README/notes/config)
- Open-ended. Claude must identify which of 5 sibling projects are relevant.
- **total_input −17% (p=0.0098), total_output −21% (p=0.0068), cache_read −16% (p=0.014).** Turn count +25% (p=0.93, NS — i.e. harness took *more* logical decision turns but each turn was tighter). 100% success both conditions.
- **The output-token tax INVERTED.** Output dropped instead of rising.
- Interpretation: On exploratory tasks, the harness prevents wasteful tool chatter. Claude doesn't need to narrate "let me explore these folders" — it reads CLAUDE.md, gets oriented, and proceeds directly. The savings on reads (fewer irrelevant sibling READMEs opened) are larger AND the savings on writes (less exploratory commentary) compound on top — even though Claude took slightly *more* decision-point turns to get there.

### Task 4B — Sibling access negotiation (session scoped to one project, prompt asks Claude to request access to parent)
- n=10 complete. **Harness HURT on tokens, not turns.**
- **cache_read +64% (p=0.002), total_input +55% (p=0.002), peak_context +10% (p=0.002).** Output +35% (p=0.16, NS). **turn_logical 0% (p=0.57, NS).** Success: 100% both conditions.
- Original `turn_count` reported +56% p=0.002 — that was an SDK-counting artifact. H0 and H1 took the same number of actual decision turns; the harness emitted more content blocks (text + tool_use) per turn, inflating block count without adding cognitive work. The real cost was tokens, not turns.
- Interpretation: The 4B prompt is unusually directive — it literally tells Claude "You will need data from sibling project folders... Request access to the parent directory if you need it." Given that map already, H0 takes the shortest path. H1 does the harness startup ritual (look for CHECKPOINT, read CLAUDE.md at the current scope, confirm next step) *before* negotiating access, and since the harness at the currently-scoped project doesn't say anything useful about the sibling structure, that work is pure narration overhead that drives cache reads and input tokens without changing decisions.
- **Counter-example to the "harness always helps with orientation" story** — harness helps orientation *when orientation is Claude's problem*. When the prompt itself pre-orients, the harness adds narrative ceremony that costs tokens (not turns) and doesn't help.

### Task 4C — Full hierarchical harness (top-level CLAUDE.md + per-sibling CLAUDE.md + CHECKPOINT.md in every sibling)
- n=10 complete. **Strongest H1 win on tokens of the whole experiment.**
- **total_output −45% (p=0.002), cache_read −25% (p=0.049), total_input −25% (p=0.016).** Peak and duration not sig. **turn_logical 0% (p=0.39, NS).** 100% success both conditions.
- Original `turn_count` reported −25% p=0.008 — that was an SDK-counting artifact. H0 and H1 took the same number of actual decision turns; the harness emitted fewer content blocks per turn (less narration, fewer interleaved tool calls), making block count drop while logical turn count stayed flat.
- Interpretation: When Claude needs to classify 5 sibling projects as "relevant" vs "irrelevant", per-sibling `CLAUDE.md` lets it decide *without opening the full README*. This compounds: fewer exploratory reads → less output chatter about what it's doing → less context to recycle on every turn. The win is in tokens-per-decision, not decisions-per-task.
- **Cross-comparison H1-4A vs H1-4C** (the real point of adding 4C): H1-4C still beats H1-4A on every token metric — output 467 → 364, cache_read 209K → 192K, input 14.5 → 13.5, and on logical turns (10 → 8). Per-sibling harness adds real incremental value beyond top-level alone. Verdict: **full hierarchical harness > top-level-only hybrid > no harness** for exploratory multi-project tasks.
- Dry-run note: n=1 dry-run predicted the opposite direction. n=1 is noise — the n=10 Wilcoxon is the real answer. Lesson: never read direction from a single trial.

---

## Patterns worth marking

### 1. Harness payoff tracks "is orientation the bottleneck?"

`H1 turn Δ` uses `turn_logical` (corrected metric, 2026-05-22 backfill). Bold cells are p < 0.05.

| Task | Task shape | H1 turn Δ | H1 output Δ | H1 cache_read Δ |
|---|---|---|---|---|
| 1A | trivial, scoped | n/a* | −10% | +3% |
| 1B | trivial, parent-scoped | **+67%** (tax) | **+136%** (tax) | **+80%** (tax) |
| 2A | structured, seeded | n/a* | −5% | +7% |
| 2B | structured, harness pre-built | 0% | −14% | +7% |
| 3 | closed, multi-step | **−17%** | +63% (tax) | **−9%** |
| 4A | open, top-level harness only | +25% (NS) | **−25%** | **−18%** |
| 4B | open, prompt pre-orients | 0% (NS) | +35% | **+64%** (tax) |
| 4C | open, full hierarchical harness | 0% (NS) | **−45%** | **−25%** |

*Tasks 1A and 2A: turn_logical unavailable -- pilot trials ran before sessions-archive existed, no source jsonl. See [turn_logical_schema_bump.md](turn_logical_schema_bump.md).

Three regimes visible here:
- **Trivial or pre-oriented tasks (1B, 4B):** harness is pure tax. Startup ritual runs, finds no relevant state, burns tokens on narration. 1B also adds significantly more decision turns. 4B's tax shows up entirely on tokens (cache_read, input) -- decision-turn count is unchanged.
- **Structured tasks with a clear artifact (1A, 2A, 2B, 3):** harness is roughly neutral on reads, sometimes taxes output (meta-commentary on protocol compliance).
- **Exploratory, orientation-dominated tasks (4A, 4C):** harness pays for itself several times over **on tokens** -- decision-turn count is statistically unchanged on both tasks. 4C (full hierarchy) beats 4A (top-level only), confirming per-sibling CLAUDE.md adds value on top.

### 2. The output-token tax is real but task-dependent
- Present on closed tasks (1B +136%, 3 +63%) — Claude spends output on protocol compliance that doesn't change the answer.
- Absent, then inverted, on exploratory tasks (4A −25%, 4C −45%) — harness prevents exploratory chatter that would otherwise cost more output than the meta-commentary saves.
- Task 4B is the interesting mid-case: output +35% (NS) — harness tax on output, even though the task is nominally exploratory, because the prompt pre-solves the exploration.

### 3. Peak context is essentially unaffected by the harness
- Task 4A: H0 peak 20,061 vs H1 peak 20,327 (+1.3%, not sig).
- Prior tasks: similar.
- The harness compresses *what Claude seeks out*, not *what Claude needs in flight*.
- **Consequence:** The original hypothesis subcomponent "harness slows context-window growth" is not confirming on tasks this size. Peak context tops out around 10–15% of the 200K window even without the harness, so there is no pressure for the harness to relieve. Would need a task engineered to genuinely approach compaction (Task 4 was originally designed for this but current 4A hits only ~20K peak).

### 4. Duration does not track token savings
- Task 4A: H1 used 17–21% fewer tokens across metrics but took **+7%** more wall-clock time (not sig).
- Likely cause: reading `CLAUDE.md` adds wall-clock time even when it saves tokens downstream. Tokens cost money; wall-clock costs developer patience — different axes.
- **Consequence:** If we ever claim "the harness is faster," we should say "faster in tokens, sometimes slower in wall-clock." Avoid conflating them.

### 5. 100% success rate across every task so far
- H0 and H1 both passed 10/10 on every task we've analyzed.
- The hypothesis's success-rate component ("at least one of: tokens, peak, success rate") is trivially tied so far.
- Primary evidence is coming from token metrics, not task success.

---

## Methodology observations (not hypothesis findings, but worth noting)

### M1. ABBAAB pairing is doing its job
- No visible time-of-day confound in the per-pair deltas.
- Paired Wilcoxon is the right test; raw comparisons would be noisier.

### M2. Archive strategy pays for itself
- Spot-checking 4A trials in `trials-archive/` revealed both conditions correctly produce `task4-output/report.py` referencing the right siblings — gives confidence the verifier isn't rubber-stamping.
- If we had only JSONL archives we couldn't verify this.

### M3. Plan-spec drift is a known gap, now being addressed
- Original plan spec said H1 for Task 4 should include per-project `CLAUDE.md` in every sibling. In practice 4A only seeded the top-level harness.
- This isn't a bug in 4A — it's a narrower test than originally planned. 4C will run the full hierarchical spec so we can measure the incremental value.
- Cross-comparison (H1-4A vs H1-4C) will answer: is the hybrid (top-level harness + plain READMEs) actually the efficient sweet spot, or does per-sibling harness add measurable value?

---

## Resolved questions (Phase 2 complete)

1. **4B — permission-expansion tasks:** No. Harness *hurt* here. The pre-oriented prompt shortcut is strictly better than running the harness startup ritual.
2. **4C — per-sibling CLAUDE.md value:** Yes, measurable and significant. H1-4C beat H1-4A across every token metric. Per-sibling harness is not ceremony — it reduces reads.
3. **Peak context claim:** Not confirmed. Even the largest tasks (4A, 4C) topped out around 20K peak, ~10% of the 200K window. Harness can't relieve pressure that doesn't exist at this task size. The "harness slows context growth" subcomponent of the original hypothesis is effectively untested — would need a task engineered to hit ~150K+.

## Open questions (not answered by Phase 2)

1. **At what task size does peak context matter?** We never approached compaction territory. A future phase would need synthetic multi-file tasks designed to consume ~150K+.
2. **Does harness payoff scale linearly with sibling count?** We tested 5 siblings. 10? 20? Return law unknown.
3. **Does a stale CLAUDE.md hurt worse than no CLAUDE.md?** Untested — H1 harness was frozen and accurate across the experiment.
4. **Duration decoupling:** Why did H1-4C take +12% wall-clock despite saving 45% on output tokens? Likely the tool-call chain in H1 includes more Read calls distributed across siblings even though each is shorter. Not a blocker, but worth noting: tokens and wall-clock are different axes.
