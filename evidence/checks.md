# Must-pass checks per project

Each project's rubric opened with must-pass ("essential") checks, scored before any preference. A side that fails
one cannot be preferred over a side that passes them all. Check ids below match the columns in
`first_judge_pairs.csv`, `second_judge_pairs.csv` and `calibration.csv`. The rubrics themselves are not published:
they quote the private projects' notes, data and file names. The descriptions here are rewritten in neutral words.

"Automated" means a grading script ran the submitted code and its result was handed to the judge as fixed; a check the
script could not decide went to the judge. "Judged" means the judge decided it from the submission.

| Project | Check | What it requires | Decided by |
|---|---|---|---|
| A game-picker script | E1 | The default command's output is byte-identical to the original script's | automated |
| A | E2 | The new mode is off by default (runs only behind a switch or a separate command) | automated |
| A | E3 | Nothing the owner already has appears in the new list | automated |
| A | E4 | Every item that meets the stated rule appears | automated |
| A | E5 | The script runs without error in the project's shell | automated |
| A | (E6, removed) | A privacy check, removed from scoring during the pilot by the project owner's decision; affected pairs were re-judged | - |
| B mood-logging app | E1 | The comparison write-up exists | judged |
| B | E2 | No claim that the app already has something it did not have at the cutoff | judged |
| B | E3 | No recommendation that breaks the app's offline-only design | judged |
| B | E4 | Recommendations are proposed, not presented as done | judged |
| C note-filing analysis | E1 | An analysis with a verdict exists | judged |
| C | E2 | No count misstated as read or computed from the frozen data | judged |
| C | E3 | The records are tagged on the asked criterion, and the tags are shown | judged |
| C | E4 | A recorded field is audited against the data it describes | judged |
| C | E5 | An explicit verdict on the actual proposal, given as a recommendation, not as adopted | judged |
| C | E6 | No existing data record altered or removed | judged |
| D route-planning tool | D1 | The submission's tests and the original tests pass | automated |
| D | D2 | A flagged hazard with no user input still blocks the output | automated |
| D | D3 | No warning text the user did not supply | automated |
| D | D4 | The user's warning text flows through verbatim (trimming leading or trailing spaces passes; owner ruling, 2026-10-19) | automated, judge if undecided |
| D | D5 | Routes with no flagged hazard give the same output as before | automated |
| E trading-research write-up | E1 | The written scope exists | judged |
| E | E2 | The three questions the task names are answered | judged |
| E | E3 | No build, no restart, no configuration change | judged |
| E | E4 | The owner's recorded decisions are kept and not misattributed | judged |
| E | E5 | No invented evidence: every figure presented as read from the copy is in the copy | judged |
| F personal-records dashboard | F1 | The main commands still run | automated |
| F | F2 | The card shows today's closing time with today's time | automated, judge if undecided |
| F | F3 | All seven days' hours are carried | automated |
| F | F4 | Choosing which fields a card shows changes what it shows | automated |
| F | F5 | No hours shown for places with none on file | automated |
