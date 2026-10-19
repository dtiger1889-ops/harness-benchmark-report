# Harness Efficacy Benchmark — Running Takeaways

Last updated: 2026-10-18 (token, cost and output corrections; see below)

Living log of what we've observed across tasks. Append on each completed task; do not rewrite the history. *Exceptions: the 2026-05-22 methods correction updated numeric claims that were SDK-counting artifacts — see the Methods correction at the top of [REPORT.md](REPORT.md); the original numbers are still in the `turn_count` column of [`results.csv`](results.csv). The 2026-10-17 token correction restated the token figures; the old ones are kept beside them, marked superseded. The 2026-10-18 output correction restated output and cost the same way.*

> **Output token correction (2026-10-18):** the 2026-10-17 recount took output from per-message log rows, which hold a partial count; each trial's final `result` event holds the complete one (input and cache tokens match it exactly on all 154 trials). Output and cost below use the complete count. Task 2B becomes a loss (cost +7%, output +41%); 1B's output gap falls from +146% to +27% (NS).

> **Token and cost correction (2026-10-17):** the CSV's original token columns summed every assistant row of each trial log, but Claude Code repeats a message's usage once per content block, so cache_read is overstated by a median 35% and cache_create by 48%. All numbers below are now counted once per message, with API-equivalent cost added, two-sided paired Wilcoxon. The corrected per-trial values are the last six columns of [`results.csv`](results.csv) (`dedup_*`, `final_output`, `cost_usd`); the method is in [REPORT.md](REPORT.md). The 2026-05-22 claim that "token-based findings are unchanged" is superseded.

---

## Headline finding (Phase 2 complete n=10 per task, 154 trials total; turns corrected 2026-05-22, tokens corrected 2026-10-17)

**The harness costs extra when the prompt already tells Claude exactly what to do, and is roughly cost-neutral everywhere else; no task got significantly cheaper.** Same frozen H1 harness: +31% cost on a trivial parent-scoped task (1B), +14% when the prompt pre-orients (4B), +7% with the harness pre-built (2B), −5% to +6% (not significant) on the exploration tasks. The significant token savings are Task 3's −13% cache reads, cancelled in dollars by +12% cache writes, and Task 1A's −10% output, outweighed by its extra cache tokens. (2026-10-17; output and cost restated 2026-10-18.)

The "turn savings/tax" framing in earlier drafts was inflated by the SDK emitting one jsonl row per content block; re-derived with `turn_logical`, Tasks 4A, 4B, and 4C show no significant difference in decision turns. The token columns carried the same per-block repetition, found 2026-10-17.

**Clearest loss:** Task 1B — cost +31% (p=0.010), cache_read +75%, cache_create +21%; output +27% (NS), turn_logical +67% (p=0.063, NS).
**Pre-oriented loss:** Task 4B (prompt already scopes the path) — cost +14%, cache_create +34% (both p=0.006); cache_read +8% (NS). Turn count unchanged (0%, p=1.0).
**No clear win.** Task 4C, previously the "clearest win," is cost +4% (p=0.63), no token metric significant.

> Superseded headline (2026-05-22, every-row sums): "**The harness helps when orientation is hard, and hurts when the prompt already tells Claude exactly what to do.** Same frozen H1 harness file went from +136% output-token tax on trivial tasks, to −45% output savings on multi-sibling exploration, to +64% cache-read tax when a prompt *explicitly instructs* Claude to request parent access." And: "Clearest win: Task 4C −45% output, −22% cache_read, −22% input, all p ≤ 0.05. Clearest loss: Task 4B +64% cache_read, +55% input, both p = 0.002."

---

## Per-task results (Phase 2, n=10 pairs unless noted)

Corrected figures are H1 vs H0 medians, counted once per message, two-sided p (2026-10-17). Superseded figures are in brackets.

### Task 1A (n=7) — Write stats.py
- Closed, one-shot, no exploration needed.
- Corrected: cost +3.9%, cache_read +4.0%, cache_create +4.8% (all p=0.016); output −10% (p=0.016, harness lower; was −11% NS before the 2026-10-18 output correction); turns 0%. A small, consistent loss of about $0.002 per trial.
- Early read (superseded framing): "no dramatic effect either direction." The 2026-05-22 note said no jsonl existed for 1A; the recount found and counted all 14 logs.

### Task 1B — Write stats.py, access scoped to parent dir
- Closed, one-shot, but Claude has to navigate up one level.
- **Corrected: cost +31% (p=0.010), cache_read +75% (p=0.027), cache_create +21% (p=0.002); output +27% (p=0.11, NS); turn_logical +67% (p=0.063, NS).** [Superseded: output +136%, cache_read +80%, input +67%, turn_logical p=0.004. Superseded 2026-10-18 (partial output counts): output +146%, cost +35%.]
- Interpretation: On tasks this simple, the harness's startup sequence (read CHECKPOINT, read project CLAUDE.md, confirm next step) is pure overhead. CHECKPOINT.md doesn't exist in the trial, so Claude spends turns looking for a file that isn't there before giving up and doing the actual (trivial) task.
- **Harness tax is real on trivial work** (in cache reads and writes; the output difference is not significant).

### Task 2A — Extract data from 3 PDFs to CSV
- n=10 complete. Neutral: cost +4% (p=0.28); no token metric significant except peak +3.4%.
- Claude needs to find the PDFs and the template, but the task is very structured once oriented.

### Task 2B — Same as 2A but harness pre-built (CLAUDE.md + empty CHECKPOINT.md seeded)
- n=10 complete. **Corrected 2026-10-18: small loss — cost +7% (p=0.020), output +41% (p=0.002);** cache and peak not significant. [Superseded 2026-10-17 figures, partial output counts: neutral, cost +4% (p=0.13), output +0.6%. Superseded first version: "Near-neutral."]
- Interpretation: A harness you *already have* doesn't help if there's nothing to orient between, and here H1 wrote more output; what the extra output says was not inspected.

### Task 3 — Complete a half-finished script
- Closed-ended but genuinely multi-step.
- **Corrected: turn_logical −17%, cache_read −13% (p=0.010)** — the largest significant token saving in Phase 2 (the other is 1A's −10% output). But cache_create +12% (NS) and output +1% (NS); **cost −5% (p=0.16), not significant.**
- [Superseded: total_input −9% (p=0.008), cache_read −9% (p=0.019), output +50%/+63%, "~12.7K net tokens saved per trial," "first task where the hypothesis is directionally supported."]
- Interpretation: H1 reads fewer cached tokens per trial, but writing its harness file into the cache costs more per token (20× a read), so the dollars come out even.

### Task 4A — Multi-project exploration (top-level CLAUDE.md only in H1, siblings have README/notes/config)
- Open-ended. Claude must identify which of 5 sibling projects are relevant.
- **Corrected: cost +6% (p=0.56); cache_read +29% (p=0.19), cache_create −3%, output −4% (p=0.56) — nothing significant.** Turn count +25% (NS). 100% success both conditions.
- [Superseded: total_input −17% (p=0.0098), total_output −21% (p=0.0068), cache_read −16% (p=0.014); "the output-token tax INVERTED."]
- Interpretation: the "harness prevents exploratory chatter" story came from the double-counted rows. On corrected numbers the top-level harness neither helps nor hurts this task.

### Task 4B — Sibling access negotiation (session scoped to one project, prompt asks Claude to request access to parent)
- n=10 complete. **Harness HURT on cost, not turns.**
- **Corrected: cost +14% (p=0.006), cache_create +34% (p=0.006), peak_context +10% (p=0.002); cache_read +8% (p=0.32, NS), output −2% (NS). turn_logical 0% (p=1.0, NS).** Success: 100% both conditions.
- [Superseded: cache_read +64% (p=0.002), total_input +55% (p=0.002), output +35%.]
- Original `turn_count` reported +56% p=0.002 — that was an SDK-counting artifact. H0 and H1 took the same number of actual decision turns.
- Interpretation: The 4B prompt is unusually directive — it literally tells Claude "You will need data from sibling project folders... Request access to the parent directory if you need it." Given that map already, H0 takes the shortest path. H1 does the harness startup ritual before negotiating access, and since the harness at the currently-scoped project doesn't say anything useful about the sibling structure, the extra harness content mostly lands as cache writes without changing decisions.
- **Counter-example to the "harness always helps with orientation" story** — when the prompt itself pre-orients, the harness adds cost and doesn't help.

### Task 4C — Full hierarchical harness (top-level CLAUDE.md + per-sibling CLAUDE.md + CHECKPOINT.md in every sibling)
- n=10 complete. **Corrected: cost-neutral.**
- **Corrected: cost +4% (p=0.63); cache_read +8% (p=1.0), cache_create +5%, output −4% (p=0.56) — nothing significant. turn_logical 0% (p=0.78, NS).** 100% success both conditions.
- [Superseded: "Strongest H1 win on tokens of the whole experiment" — total_output −45% (p=0.002), cache_read −25% (p=0.049), total_input −25% (p=0.016).]
- Original `turn_count` reported −25% p=0.008 — that was an SDK-counting artifact.
- **Cross-comparison H1-4A vs H1-4C** (unpaired H1 medians, corrected): H1-4C takes fewer turns (10 → 8) and reads less (cache_read 169K → 143K; output about level, 2,256 → 2,228) but writes more (cache_create 9.9K → 10.9K), so cost is level ($0.141 → $0.145, +2.8%). Per-sibling harness cuts reading, not cost. [Superseded: output 467 → 364, cache_read 209K → 192K, input 14.5 → 13.5, "beats H1-4A on every token metric"; verdict "full hierarchical harness > top-level-only hybrid > no harness." Superseded 2026-10-18: output 401 → 290, cost $0.111 → $0.113.]
- Dry-run note: n=1 dry-run predicted the opposite direction. n=1 is noise — the n=10 Wilcoxon is the real answer. Lesson: never read direction from a single trial.

---

## Patterns worth marking

### 1. Harness cost tracks "is orientation already solved?"

Corrected 2026-10-17 (counted once per message, two-sided p); cost restated 2026-10-18 with complete output counts. `H1 turn Δ` uses `turn_logical`. Bold cells are p < 0.05.

| Task | Task shape | H1 turn Δ | H1 cost Δ | H1 cache_read Δ | H1 cache_create Δ |
|---|---|---|---|---|---|
| 1A | trivial, scoped | 0% | **+4%** | **+4%** | **+5%** |
| 1B | trivial, parent-scoped | +67% (tax, p=0.063) | **+31%** (tax) | **+75%** (tax) | **+21%** (tax) |
| 2A | structured, seeded | 0% | +4% | +3% | +5% |
| 2B | structured, harness pre-built | 0% | **+7%** (tax) | +2% | +4% |
| 3 | closed, multi-step | **−17%** | −5% | **−13%** | +12% |
| 4A | open, top-level harness only | +25% (NS) | +6% | +29% | −3% |
| 4B | open, prompt pre-orients | 0% (NS) | **+14%** (tax) | +8% | **+34%** (tax) |
| 4C | open, full hierarchical harness | 0% (NS) | +4% | +8% | +5% |

Turn deltas for 1A and 2A come from the `dedup_messages` column; their `turn_logical` cells are blank because those trials ran before that column existed.

> Superseded table (2026-05-22, every-row sums) — output Δ / cache_read Δ: 1A −10% / +3%; 1B +136% / +80%; 2A −5% / +7%; 2B −14% / +7%; 3 +63% / −9%; 4A −25% / −18%; 4B +35% / +64%; 4C −45% / −25%.

What's visible now:
- **Trivial or pre-oriented tasks (1B, 4B):** harness is pure tax. Startup ritual runs, finds no relevant state, and pays for it — mostly in cache writes of its own files. 1B also adds more decision turns (+67%, two-sided p=0.063, not significant).
- **Structured tasks (1A, 2A, 2B, 3):** roughly neutral, except 2B's small loss from extra output; Task 3 reads less but writes more.
- **Exploratory tasks (4A, 4C):** cost-neutral. The earlier "harness pays for itself several times over on tokens" was the double counting.

### 2. No consistent output-token tax
- Corrected 2026-10-18 (complete output counts): significant only in 2B (+41%, p=0.002) and 1A (−10%, p=0.016), opposite directions. 1B +27% (NS); 3, 4A, 4B, 4C within ±4%.
- [Superseded: "present on closed tasks (1B +136%, 3 +63%), inverted on exploratory tasks (4A −25%, 4C −45%)." Superseded 2026-10-18 (partial output counts): "only 1B is significant (+146%)".]
- Output is 10–26% of a trial's cost (about 500–2,300 tokens per trial); cache reads and writes are the rest.

### 3. Peak context is essentially unaffected by the harness
- Task 4A: H0 peak 20,017 vs H1 peak 20,134 (+0.6%, not sig). Peak values are unchanged by the 2026-10-17 correction (it is a per-call maximum, not a sum). [Earlier draft: 20,061 vs 20,327.]
- H1 raises peak slightly in five tasks (+3% to +10%, significant in 1A, 1B, 2A, 3, 4B) because its files sit in context.
- **Consequence:** The original hypothesis subcomponent "harness slows context-window growth" is not confirming on tasks this size. Peak context tops out around 10–15% of the 200K window even without the harness, so there is no pressure for the harness to relieve.

### 4. Duration does not track tokens
- Task 4A: H1 took about +7% more wall-clock time (not sig); 4C about +12%. With corrected tokens, H1 was not cheaper on either.
- Reading `CLAUDE.md` adds wall-clock time. Tokens cost money; wall-clock costs developer patience — different axes.
- [Superseded: "H1 used 17–21% fewer tokens across metrics but took +7% more wall-clock time"; "faster in tokens, sometimes slower in wall-clock."]

### 5. 100% success rate across every task
- H0 and H1 both passed 10/10 on every task.
- The hypothesis's success-rate component is trivially tied. Primary evidence is token and cost metrics.

### 6. Count each message once (added 2026-10-17)
- Claude Code writes one log row per content block (text, each tool call) and copies the message's full usage onto each. Summing rows double- or triple-counts. Any future bench must dedupe by `message.id`, take output from the final result record, and price cache writes and reads separately. The shipped `bench/run-trial.ps1` still sums every row.

---

## Methodology observations (not hypothesis findings, but worth noting)

### M1. ABBAAB pairing is doing its job
- No visible time-of-day confound in the per-pair deltas.
- Paired Wilcoxon is the right test; raw comparisons would be noisier.

### M2. Archive strategy pays for itself
- Spot-checking 4A trials in `trials-archive/` revealed both conditions correctly produce `task4-output/report.py` referencing the right siblings — gives confidence the verifier isn't rubber-stamping.
- The archived JSONLs also made the 2026-10-17 token correction possible.

### M3. Plan-spec drift is a known gap, now being addressed
- Original plan spec said H1 for Task 4 should include per-project `CLAUDE.md` in every sibling. In practice 4A only seeded the top-level harness.
- This isn't a bug in 4A — it's a narrower test than originally planned. 4C ran the full hierarchical spec to measure the incremental value.

---

## Resolved questions (Phase 2 complete)

1. **4B — permission-expansion tasks:** No. Harness *hurt* here (+14% cost). The pre-oriented prompt shortcut is strictly better than running the harness startup ritual.
2. **4C — per-sibling CLAUDE.md value:** Corrected 2026-10-17: it cuts reading and turns versus top-level-only, but not cost (+2.8%), and neither layout beats no harness on cost. [Superseded: "Yes, measurable and significant... beat H1-4A across every token metric."]
3. **Peak context claim:** Not confirmed. Even the largest tasks (4A, 4C) topped out around 20K peak, ~10% of the 200K window. The "harness slows context growth" subcomponent of the original hypothesis is effectively untested — would need a task engineered to hit ~150K+.

## Open questions (not answered by Phase 2)

1. **At what task size does peak context matter?** We never approached compaction territory. A future phase would need synthetic multi-file tasks designed to consume ~150K+.
2. **Does harness cost or benefit change with sibling count?** We tested 5 siblings.
3. **Does a stale CLAUDE.md hurt worse than no CLAUDE.md?** Untested — H1 harness was frozen and accurate across the experiment.
4. **Does the harness pay off across sessions?** Every Phase 2 trial was one fresh session; resuming work is the harness's purpose, and this benchmark did not test it.
