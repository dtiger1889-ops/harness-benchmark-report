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
| [task-specs.md](task-specs.md) | Qualitative spec of each benchmark task and why it exists |
| [takeaways.md](takeaways.md) | Condensed practical guidance derived from the results |
| [results.csv](results.csv) | Per-trial raw results (phase 2, tasks 1-4) |

## Why you might care

If you maintain persistent instruction files for a coding agent (Claude Code, Cursor rules, AGENTS.md, etc.), this is empirical evidence about when that investment pays off and when it actively hurts. The companion tooling that implements the pattern lives at [claude-harness-toolbox](https://github.com/dtiger1889-ops/claude-harness-toolbox).

## License

MIT. See [LICENSE](LICENSE).
