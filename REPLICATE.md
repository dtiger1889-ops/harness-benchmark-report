# Replicating the six-project test on your own projects

This is how to rerun the study in [PAPER.md](PAPER.md) on your own repositories with the scripts in [kit/](kit/).
The original six project packets are private and not included; you build packets from your own projects.

**How far this kit has been checked.** It was checked through arm building: `build_arms.py` built both arms of a
small toy project and passed both of its audits, `test_outside_paths.py` passes, and every script starts and reads
its config. A full trial and judge call was not re-run for this kit, so the first real trial on your setup is also
the kit's first end-to-end run. Start with one pair (step 7) before a whole run, and run the kit from a plain
terminal: an AI coding tool's own safety checks may refuse to let an agent session set up or launch these runs.

## What you need

- Python 3.10 or newer (standard library only; `figures/` additionally needs matplotlib).
- An AI coding CLI that runs headless with the flags the scripts use. The kit was built for Claude Code
  (`claude -p`, `--setting-sources`, `--strict-mcp-config`, `--tools ""`, `--output-format stream-json`). Another
  CLI needs the two launch commands in `run_trial.py` and `run_judge.py` changed.
- Your own projects in git, each with its notes in a short instruction file plus a separate state file (or whatever
  two-level layout you want to test against a single file).
- Windows, or the patience to extend one regular expression: the outside-path audit in `run_trial.py` recognizes
  Windows drive paths and MSYS-style paths (`/c/...`). On macOS or Linux, extend `outside_paths()` to catch
  absolute POSIX paths before you trust its void flags.

## 1. Set up the config

Copy `kit/kit_config.example.json` to `kit/kit_config.json` (or point the `KIT_CONFIG` environment variable at a
copy) and fill in:

- `root`: an empty folder that will hold `packets/`, `judge_only/`, `results/` and `runs.json`.
- `trials_dir` and `done_dir`: two more empty folders, both **outside** `root`. A trial runs in `trials_dir`, so
  it must not be able to reach the results or the judge-only evidence through `..` or git.
- `worker_model`, `judge_model`, `judge_effort`, `claude_cmd`.
- `forbidden_launch_roots`: folders the judge must never start in (your own project folders).
- `leak_patterns`: names of your private folders; a worker tool call naming one voids the trial.
- `benign_prefixes`: tool install folders a worker may touch without voiding (leave empty to start).

Run `python kit/test_outside_paths.py` once; it should print `failures: 0`.

## 2. Pick projects and a freeze point (decide the rules first)

Write your selection rule, outcome, void, replacement and stop rules down **before** you look at candidates, and
do not change them after the first trial. The rule the paper used from run 2 on:

1. Your own repository, with its notes files committed at the cutoff commit.
2. The next milestone was written down (in the notes, a spec or a roadmap) before the cutoff and finished in a
   later commit.
3. Doable in one headless session from the frozen copy alone: no login, secret, live service or web. Give anything
   that needs live data a synthetic fixture, or drop the candidate.
4. The single merged notes file stays far below the context limit (the paper used about 40k tokens), and the tree
   is small enough to copy per trial.
5. The finished milestone added or changed at least 60 lines of real project content.
6. Pick order among qualifying projects is fixed in advance (the paper: write-up milestones first, then the larger
   finished milestone, then name), so you cannot steer toward a favorable project.

The project, not the trial, is the independent unit. More projects buy more evidence than more repeats.

## 3. Cut a packet

For each project, make `root/packets/<id>/` with:

- `freeze/`: the repository at the cutoff commit (`git archive <cutoff> | tar -x -C freeze`), minus `.git` and
  anything private the milestone does not need. Check that nothing you drop holds a fact the task depends on.
- `fixture/` (optional): synthetic files laid over the freeze in both arms, at the same relative paths.
- `brief.txt`: the task, quoting the milestone as written in the notes, plus any constraint the copy imposes (no
  network, which interpreter to use). End with the instruction to finish, check, and record the work the way the
  project keeps it.
- `packet.json`: see `kit/examples/packet.example.json`. `sources` lists the notes files to merge, in order, with a
  heading each; `drops` lists the patterns that only make sense with two files (pointers to the state file, version
  stamps); `facts` lists one regular expression per fact in your fact inventory; `kind` is `write-up` or `coding`.
- `judge_rubric.md`: see step 5.

Then make `root/judge_only/<id>/` holding the reference evidence the judge sees (for example the diff of the commit
that finished the milestone, as a text file), and a `fixtures/` folder for step 6. Nothing under `judge_only` is
ever copied into a trial.

## 4. Build both arms

```
python kit/build_arms.py <id>
```

This writes `packets/<id>/arms/harness` (the freeze plus fixture, unchanged) and `packets/<id>/arms/bloat` (the
same, with the notes files replaced by one merged `CLAUDE.md`), prints every dropped line, and writes
`fact_audit.json`. It exits 0 only if every fact appears in both arms, the merged file holds every source line in
order and nothing else, and no other file differs. Read the dropped lines yourself, and have a second person or
model re-check the fact inventory against both arms.

## 5. Write the rubric

Start from `kit/examples/judge_rubric_template.md`. It holds the brief, the project facts, what not to score, the
reference evidence note ("one good answer, not the only one"), the must-pass checks and the preference dimensions.
Write it before any trial runs. Must-pass checks should be things a stranger could verify from the submission: the
artifact exists, nothing claimed that the project did not have, a default behavior unchanged, no project rule broken.
For coding milestones, a grading script can decide checks by running the submitted code: set `grader` in
`packet.json` to a command list, last item the script path relative to the packet folder (use `"python"` as the first
item to mean the kit's interpreter). It is called with `--trial <dir> --packet <packet dir>` and must print JSON
`{"checks": {"<id>": "pass" | "fail" | "manual"}}`. A `manual` check goes to the judge.

## 6. Make calibration fixtures

In `judge_only/<id>/fixtures/`, make one folder per fixture. Each is a complete copy of the project tree (the
freeze plus fixture overlay) as a submission would leave it: the judge packet is built by diffing it against the
freeze, so a file left out reads as deleted. All five below are required; calibration is not clean with one missing.

- `known_good`: the real finished milestone.
- `missing` (write-up packets) or `untouched` (coding packets): nothing done.
- `polished_wrong`: well written but breaks a must-pass check.
- `valid_alternative`: a different, defensible answer.
- `padded`: `known_good` with filler, about twice the length, no new facts.
- `sentinel` (optional): `known_good` plus a file that names its arm; the judge must refuse it.

Then run:

```
python kit/run_driver.py fixtures
```

Every fixture pair is judged in both orders. It exits 3 on any miss (the known-good side not preferred, the padded
side preferred, identical outputs not a tie, or must-pass results not as expected). Fix the rubric and rerun until it
is clean. Trials and judging refuse to start while calibration is not clean or any rubric, grader, packet or
evidence file has changed since.

## 7. Run trials

Copy `kit/examples/runs.example.json` to `root/runs.json` and name your packets. Then:

```
python kit/run_driver.py trials --run run1 --max-trials 2
```

`--max-trials` runs a batch and stops, so you can watch your usage limits between batches; rerun the same command to
continue. Each trial copies its arm into `trials_dir`, runs the worker headless, records a row in
`results/v4-results.csv` (total tokens included), saves the transcript and changed files, audits the transcript for
outside references, and moves the copy to `done_dir`. A voided trial's pair is dropped. If a project ends short of its
pair target, add one replacement pair per void among the first pairs (raise `pairs_per_packet`), once.

## 8. Judge both orders

```
python kit/run_driver.py judge --run run1
```

Every valid pair is judged twice, harness shown first and comparison shown first. Results go to
`results/run1/judge_summary.json`. If a packet's text contains words that could hint at an arm, the driver stops
and reports that a review is needed: read the hits listed in the packet's `cue_audit`, and if they are harmless,
record that in `results/run1/cue_reviews.json` as `{"<packet file name>": {"cue_hash": "<value>"}}`, where the value
is what `cue_hash()` in `run_driver.py` returns for that packet file. A packet whose text names an arm outright is
always refused.

## 9. Tally

```
python kit/tally.py run1
```

Prints pair verdicts (a side wins only when both orders pick it), project leans, the two-sided exact sign test over
the leaning projects, must-pass failures and median total tokens per arm per project. Pool several runs by naming
them all.

## A second judge

The paper's second judge re-sent each saved prompt (`results/<run>/judge/*.prompt.txt`) unchanged to a model from
another family and parsed the answer with the same strict parser. That script was tied to one machine's setup and
is not included; any CLI that takes a prompt on stdin and returns text can do the same.
