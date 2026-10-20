# Why each pair went the way it did

The judges returned a free-text reason with every verdict. Those reasons quote the private projects (file names,
records, people, places), so they are not published verbatim. Below is each judged pair's reason rewritten in neutral
words, keeping what decided it. The structured verdicts (both orders, confidence, must-pass failures) are in
`first_judge_pairs.csv` and `second_judge_pairs.csv`. "Harness" and "comparison" are the two arms (see the paper,
section 3). Confidence is the first judge's, given per order; one value means both orders gave it.

Submission excerpts are not published at all. Every submission is a change to a private project's own files, and
even the code carries that project's names and data; no excerpt survived the privacy cut intact enough to be
useful. The failure types are described in words instead.

## Pilot (apparatus check; not part of the project leans)

| Pair | Verdict | Confidence | What decided it |
|---|---|---|---|
| smoke-B-p1 | harness | high | The comparison side claimed the app already had two features it did not have (fails B-E2), and wrongly said the app's source code was missing from its folder. |
| pilot-B-p2 | harness | low | Both passed every check and reached nearly the same picks; the harness side kept a project rule about interface wording and tied more ideas to the app's spec. |
| pilot-A-p1 | harness | medium | The harness side applied the filter the notes asked for and gave the literal commands from the project's procedure file; the comparison side let excluded items through and invented a page build script. First judged for the comparison side on a privacy check that was then removed from scoring (see `checks.md`); re-judged. |
| pilot-A-p2 | harness | medium | Same working script and same output list; the harness side gave literal commands, the comparison side described them in prose. |

## Run 1: projects A and B

| Pair | Verdict | Confidence | What decided it |
|---|---|---|---|
| main-A-p1 | harness | high | The comparison side computes the new list on every default run (fails A-E2, off by default) and invented a page and build script. |
| main-A-p2 | harness | low / medium | Both sides fail A-E2. Same output; the harness side was more candid that its filter lets some excluded items in. |
| main-A-p5 | comparison | medium | The harness side invented a page template and build script and rewrote a step of the project's procedure around them; the comparison side said plainly the page did not exist. |
| main-A-p6 | harness | medium | Same data step and output; this time the comparison side invented the page template and the harness side said plainly it was absent. |
| main-A-p7 | comparison | low | The comparison side's threshold matched the stated intent; the harness side's looser threshold padded the list. |
| main-B-p1 | harness | low | Both pass; the harness side kept an unbuilt feature separate from what exists and placed more of the source's ideas. |
| main-B-p2 | harness | low | The harness side paired its main pick with a cheap first step; the comparison side had small factual slips. |
| main-B-p4 | tie | medium | Same defensible answer; the comparison side slightly more concrete, the harness side no worse. |
| main-B-p5 | harness | high | The comparison side claimed the app already had two features it lacked (fails B-E2). |
| main-B-p6 | harness | low | The harness side kept the interface-wording rule and placed every idea. |

## Run 2: projects C and D

| Pair | Verdict | Confidence | What decided it |
|---|---|---|---|
| run2-C-p1 | harness | medium | The comparison side presented its verdict as already adopted, edited a live instruction file to match, and restated the proposal's success measure (fails C-E5). |
| run2-C-p2 | harness | medium | Same verdict; the harness side showed every tag, admitted it tagged after seeing outcomes, ran a sensitivity check and left the live file alone. |
| run2-C-p3 | harness | medium | Similar verdicts; the harness side shipped a read-only script that reproduces every count. |
| run2-C-p4 | harness | low / medium | The comparison side had the sharper analysis, but edited the live instruction file and called the rule fixed without proposing it to the owner. |
| run2-D-p1 | harness | low | Near-identical builds; the harness side turned malformed input into named errors. |
| run2-D-p2 | harness | medium | The harness side keeps the output invalid when a user entry matches no flagged hazard; the comparison side only prints a note. |
| run2-D-p4 | comparison | medium | Both pass; the comparison side lets the user clear a safe hazard with a reason and flags stale entries after a route change, while the harness side silently turned unmatched entries into extra markers. |
| run2-D-p5 | harness | low | Same mechanism; the harness side writes a fill-in template of every flagged hazard without overwriting one. |

## Run 3: projects E and F

| Pair | Verdict | Confidence | What decided it |
|---|---|---|---|
| run3-E-p2 | comparison | low | Same core answer; the comparison side separated two readings of the question's key term more clearly and treated one premise as untested. |
| run3-E-p4 | tie | low / medium | The two orders disagreed (comparison, then tie), so a tie by rule. Near-identical conclusions; the harness side had the better staged experiment, the comparison side the better comparison of options. |
| run3-E-p5 | comparison | medium | The harness side fails E-E5 (no invented evidence): it cites an operating-cost figure from an older period, about a quarter of what the frozen notes record. |
| run3-F-p1 | harness | medium | The harness side added the real data columns and refuses hours it cannot parse; in one order the judge also failed the comparison side on F-F2 (closing time shown only while the place is open). |
| run3-F-p2 | comparison | medium | Both pass; the comparison side works out "today" and the closing time in the browser from the viewer's clock, while the harness side fixes them when the page is built, so a page left open goes stale. |

## Second judge: the four disagreements (runs 1-2 close calls)

| Pair | First judge | Second judge (harness shown first / comparison shown first) | What the second judge saw |
|---|---|---|---|
| main-A-p7 | comparison | harness / comparison (split) | A genuine close call: in one order it weighted the harness side's stricter filter, in the other the comparison side's default threshold. |
| main-B-p4 | tie | harness / harness | It found the comparison side's description of the app's scales and backup code less accurate. |
| run2-C-p3 | harness | comparison / harness (split) | In one order it failed the harness side on C-E3 for leaving one record untagged; in the other it failed both sides on C-E3 and preferred the harness side. Both sides had left out the same record, which was not one of the scored proposals. |
| run2-D-p5 | harness | comparison / comparison | First it failed the harness side on D-D4 because its loader trims spaces from the user's text. Re-judged under the owner's ruling that trimming passes, the pick stayed comparison, now on quality: the comparison side places the warning on the nearest route segment rather than the nearest route point, and rejects malformed text instead of dropping it. |
