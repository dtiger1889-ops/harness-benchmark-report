# Task Specs Reference

Qualitative purpose of each task in the harness-efficacy benchmark. Recreated from the original project plan and extended with Task 4C, which was added mid-experiment to resolve plan-spec drift in Task 4A.

Every task was run n=10 paired trials (n=7 for 1A, the Phase 1 pilot) in ABBAAB alternating order. Same prompt across H0 and H1; only difference is what files exist in the trial root when Claude starts.

## Full task matrix

| # | Setup | H0 template | H1 template | End condition |
|---|-------|-------------|-------------|---------------|
| **1A** | Fresh project dir, no seed files, access scoped to project dir only. | Empty directory. | Top-level `CLAUDE.md` only (frozen H1-base harness). | A working non-trivial Python script exists (e.g. fetch top 5 HN stories, print title + score); passes `python script.py` with non-empty stdout. |
| **1B** | Same as 1A but access scoped to a **parent** dir containing the (empty) project folder — tests whether Claude looks outside the immediate cwd. | Empty parent + empty child. | `CLAUDE.md` at parent; no per-project harness. | Same as 1A. |
| **2A** | Project dir pre-seeded with 3 sample PDFs + an empty CSV template. Extraction task. | Seeds only. | Seeds + top-level `CLAUDE.md`. | CSV populated, row count == rows extracted from PDFs, headers match template. |
| **2B** | Same seeds as 2A, but H1 ships with the harness **pre-built** (pointers only, no task answers). Tests whether an already-materialized harness accelerates orientation. | Seeds only. | Seeds + top-level `CLAUDE.md` + per-project `CLAUDE.md` + empty `CHECKPOINT.md`. | Same as 2A. |
| **3** | Project dir contains a half-finished Python script (identical across conditions, snapshotted from a browser Claude session). Completion task with a functional check. | Seed script only. | Seed script + top-level harness. | Completed script passes its predetermined functional check. |
| **4A** | Top-level dir contains 5 sibling project folders — 3 irrelevant (notes/readme/config), 2 relevant (Q1/Q2 sales CSVs). Task requires identifying the relevant ones and combining their data. **Hybrid H1**: top-level harness only; siblings keep their plain README/notes/config files, no per-sibling harness. | Siblings exist, no harness anywhere. | Top-level `CLAUDE.md` only; siblings have plain `README.txt`/`notes.txt`/`config.txt`/`readme.txt`. | New `task4-output/` folder created, `report.py` script reads and combines data from the 2 relevant siblings and prints a summary. |
| **4B** | Same sibling structure as 4A, but session starts **scoped to one sibling** and the prompt explicitly tells Claude to request access to parent/siblings. Tests permission-expansion handling. | No harness anywhere. | Top-level `CLAUDE.md` + per-sibling `CLAUDE.md` in every sibling (full harness). | Same artifact as 4A. |
| **4C** (added mid-experiment) | Same prompt and sibling structure as 4A. **Full hierarchical H1**: top-level harness AND per-sibling `CLAUDE.md` + `CHECKPOINT.md` in every sibling. Exists to resolve plan-spec drift in 4A and to isolate the incremental value of per-sibling harness vs top-level-only. | Siblings exist, no harness anywhere (identical to 4A's H0). | Top-level `CLAUDE.md` + per-sibling `CLAUDE.md` + per-sibling `CHECKPOINT.md` in every sibling. | Same artifact as 4A. |

## Prompt locations

- `C:\bench\prompts\task1A.txt` through `task4C.txt` — one canonical prompt per task, read by the runner at trial time. Never modified during the experiment. Task 4C's prompt is byte-for-byte identical to 4A's (the only difference between 4A and 4C is the H1 template).

## Template locations

- `C:\bench\templates\H0-empty\` — empty baseline for all tasks.
- `C:\bench\templates\H1-base\CLAUDE.md` — frozen v1 top-level harness, stripped of any references to the author's real projects. Reused by every H1 trial in tasks 1A, 1B, 2A, 2B, 3, and 4A.
- `C:\bench\templates\seeds\task{1B,2A,2B,3,4A,4C}\` — per-task seed files (PDFs for 2A/2B, half-finished script for 3, sibling folders + data for 4A/4C).
- `C:\bench\templates\H1-task4C\` — full self-contained H1 template for 4C. Contains top-level CLAUDE.md + 5 sibling folders with per-sibling CLAUDE.md + CHECKPOINT.md each. Only task that has a full-template override; every other task uses the H1-base + seeds composition path.

## Why 4C was added

The original plan spec called for Task 4's H1 to have per-project `CLAUDE.md` "in every sibling", but 4A's implementation only seeded a top-level CLAUDE.md with plain README/notes/config files in the siblings — effectively a "hybrid" harness. This was not a bug in 4A's data (the numbers are valid for what was tested), but it meant 4A alone couldn't answer whether the full hierarchical harness pattern the author actually uses in `Projects/` adds measurable value beyond a single top-level harness file.

4C was designed as strictly additive: same prompt, same verifier, same sibling data as 4A, with the full hierarchical H1 spec. The **cross-comparison H1-4A vs H1-4C** (not just H0-4C vs H1-4C) is where the answer lives.

## Verifier locations

- `C:\bench\verifiers\task{1A,1B,2A,2B,3,4A,4B,4C}.ps1` — per-task pass/fail scripts. Return exit 0 on pass, non-zero on fail. 4C's verifier is byte-for-byte identical to 4A's.

## End-of-trial artifacts (for each trial)

1. Session JSONL → `C:\bench\sessions-archive\<trial-name>.jsonl` (primary source of truth for per-turn detail).
2. Full trial folder → `C:\bench\trials-archive\<trial-name>\` (for manual inspection of Claude's actual outputs when a result looks anomalous).
3. Row appended to `C:\bench\results.csv` (unless `-DryRun` switch was passed to the runner).
4. Live trial directory deleted.
