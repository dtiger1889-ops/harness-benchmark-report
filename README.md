# Does a memory harness make coding agents cheaper? A paired benchmark

This repo contains the full write-up and data for a controlled experiment measuring whether a lightweight "memory harness" (persistent `CLAUDE.md` instruction files plus a `CHECKPOINT.md` state file) changes the cost and reliability of LLM coding-agent sessions.

**Design:** 154 paired trials across 8 task types (closed implementation tasks, exploratory orientation tasks, resume-from-cold-start tasks), each run with and without the harness under otherwise identical conditions. Primary metrics: output tokens and logical decision turns. Significance via Wilcoxon signed-rank on the paired differences.

**Headline results** (details and caveats in [REPORT.md](REPORT.md)):

- Exploratory, orientation-dominated tasks: the harness pays for itself several times over on tokens; a full per-project hierarchy beats a single top-level file.
- Closed, fully-specified tasks: the harness is a net tax; loading state the task does not need costs tokens with no quality gain.
- Resume tasks: the state file is the difference between continuing work and re-deriving it.

## Files

| File | What it is |
|---|---|
| [REPORT.md](REPORT.md) | The full report: design, methodology, per-task results, statistics, limitations |
| [REPRODUCE.md](REPRODUCE.md) | Step-by-step instructions for re-running the whole thing from scratch |
| [bench/](bench/) | The benchmark itself: trial runner, frozen prompts, verifiers, harness templates, seed data, analyzer |
| [task-specs.md](task-specs.md) | Qualitative spec of each benchmark task and why it exists |
| [takeaways.md](takeaways.md) | Condensed practical guidance derived from the results |
| [results.csv](results.csv) | Per-trial raw results (phase 2, tasks 1-4) |

## Reproducing it

The experiment is not just described here, it ships here. [`bench/`](bench/)
holds the actual runner, the eight frozen prompts, the pass/fail verifiers, both
harness templates, the seed data, and the analyzer — the same files that
produced [results.csv](results.csv). [REPRODUCE.md](REPRODUCE.md) walks the run
end to end: prerequisites, a smoke test before you spend money, the `ABBAAB`
pairing sequence, the pre-registered decision rule, the failure modes that
silently corrupt a run, and how to add your own harness variant or task.

## Why you might care

If you maintain persistent instruction files for a coding agent (Claude Code, Cursor rules, AGENTS.md, etc.), this is empirical evidence about when that investment pays off and when it actively hurts.

The pattern these trials measure — `CLAUDE.md` for stable rules, `CHECKPOINT.md` for mutable state, hooks that enforce them — is implemented as installable tooling at **[claude-harness-toolbox](https://github.com/dtiger1889-ops/claude-harness-toolbox)**. This repo is the evidence; that repo is the thing the evidence is about. Read [REPORT.md](REPORT.md) § Recommendations before installing it: the honest answer is that it helps on some shapes of work and costs you tokens on others.

## License

MIT. See [LICENSE](LICENSE).
