# Audit history

Every stage of the benchmark, from the apparatus before the pilot to the run-3 results, was audited by a second model
(Codex Sol, a different model family from the worker and the first judge). The auditor read the code, the plans and the result files and reported
findings; the operator then checked each finding against the code and fixed or rejected it. The audit reports themselves
are not published because they quote file paths and contents of the private project copies; this table summarizes them.

| Date | What was audited | Findings | Outcome |
|---|---|---|---|
| 2026-10-17 | Pilot apparatus, before any real judging | 13 | 12 confirmed and fixed, 1 rejected (a string the auditor read as a shell pattern) |
| 2026-10-17 | Pilot follow-up (the fixes above) | 11 | 11 confirmed and fixed |
| 2026-10-17 | Run 1 (main run), first pass | 7 | 7 confirmed and fixed |
| 2026-10-17 | Run 1 fixes and results write-up | 4 | 4 confirmed and fixed |
| 2026-10-17 | Token metric and the results dashboard | 4 | 4 confirmed and fixed |
| 2026-10-17 | Run 2 rules, frozen before screening | 8 | 8 confirmed and fixed before any candidate was picked |
| 2026-10-17 | Run 2 project pick | 2 | 2 confirmed and fixed (documentation) |
| 2026-10-17 | Run 2 task packets | 8 | 8 confirmed and fixed before the first trial |
| 2026-10-18 | Run 2 execution and write-up | 4 | 4 confirmed and fixed |
| 2026-10-18 | Run 2 fixes (blind review page) | 1 | 1 confirmed and fixed |
| 2026-10-18 | Review page parser | 0 | clean |
| 2026-10-19 | Run 3 and the Phase 2 public correction | 3 | 2 fixed (grader false passes, then calibration re-run and both affected pairs re-judged with no change); 1 recorded as a deviation (see the paper, section 7) |
| 2026-10-20 | Design of the coming notes-vs-no-notes test | 11 | 11 fixed in the design before anything was built |

## What the audits caught that would have changed results

- **Stale results reused silently.** The first driver skipped any step whose output file already existed, so a
  changed rubric could be judged with old grader output. Fixed: a calibration fingerprint over rubrics, graders
  and packets, and a judge result is reused only if its prompt is byte-identical.
- **A grader that passed broken code.** The game-picker grader ran only the default command, so a buy mode
  that did not work could pass from a stale output file. Fixed to re-run the new mode; three run-1 trials then
  failed the "off by default" check that had passed them before.
- **Replacement pairs decided after the voids.** In run 1 the rule for replacing voided pairs was set after the
  first voids were seen. It could not be undone, so run 1 is reported both with and without the replacements, and
  from run 2 on the replacement rule was frozen before collection and enforced in code.
- **A void rule that read paths too loosely and too strictly.** The outside-folder detector missed some path forms
  and misread others (a `sed` pattern read as a folder voided a trial that was then restored). Each case became a
  test in the kit's `test_outside_paths.py`.
- **Two grader false passes in run 3.** The personal-records grader accepted a wrong closing time when a nearby
  time matched, and could not see hours drawn by a script. Fixed, calibration re-run, both pairs re-judged; the
  picks did not change.
