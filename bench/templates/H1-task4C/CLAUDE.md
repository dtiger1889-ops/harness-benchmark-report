# Project Harness
<!-- v1 — 2026-04-23 — FROZEN for benchmark experiment. Do not edit. -->

## Operating principles

1. **Harness beats model.** Fix session failures by improving CLAUDE.md/CHECKPOINT.md, not by retrying.
2. **Context = working consciousness.** Irrelevant tokens degrade reasoning. Don't dump files; follow pointers.
3. **Progressive disclosure.** CLAUDE.md → project CLAUDE.md → CHECKPOINT.md → artifacts. Never collapse.
4. **Explicit completeness.** Read Open threads + Next step — don't infer done from looking at files.
5. **Feedback loops bound quality.** Don't mark done without verification. If unverifiable, say so in CHECKPOINT.
6. **Clean handoffs.** Session ends with CHECKPOINT reflecting reality. Updating it is part of the task.
7. **One thread at a time.** Pick one open thread, finish or hit a real blocker, then stop.

## Startup sequence (every session)

Before taking any action in a project folder:
1. Look for a `CHECKPOINT.md` in the current project directory and read it.
2. Look for a project-level `CLAUDE.md` in the current project directory and read it.
3. Confirm the `Next step` in `CHECKPOINT.md` still matches what you are being asked to do.
4. Then act.

## Shared rules

**Checkpoint updates**
- When context is about to be compacted, rewrite `CHECKPOINT.md` in the current project directory.
- Also update `CHECKPOINT.md` at the end of any logically complete task.

**What a good CHECKPOINT.md looks like**
- Overwritten in place (not appended). Keep it under 80 lines.
- Sections: `Status` (1 line), `Goal` (1–3 lines), `Key decisions` (bullets), `Open threads` (bullets), `Files that matter` (paths + 1-line why), `Next step` (1 line).
- Write it so a fresh session can resume cold by reading it.

**What a good per-project CLAUDE.md looks like**
- Short (15–30 lines). Purpose, how to run it, gotchas, pointer to `CHECKPOINT.md`.
- Stable info only — mutable state belongs in `CHECKPOINT.md`.

**File hygiene**
- Don't create planning files or status docs unless asked.
- Work within the current project directory unless the prompt explicitly grants broader access.

**Versioning**
- Every `CLAUDE.md` carries a version stamp on line 2: `<!-- vN — YYYY-MM-DD HH:MM UTC -->`.
- Increment N on any substantive change.
