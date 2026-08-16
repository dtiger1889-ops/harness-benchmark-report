Last updated: 2026-04-23 23:45 UTC

## Status
Static reference data. No active work in progress.

## Goal
Preserve Q2 sales figures as an immutable, readable source for downstream reporting.

## Key decisions
- Schema deliberately matches `proj-relevant-1/sales_q1.csv` so the two can be concatenated.
- Same region/product pair can appear in both quarters — treated as two independent data points, not duplicates.

## Open threads
- None.

## Files that matter
- `sales_q2.csv` — the data.
- `README.txt` — short pointer for consumers.

## Next step
None — reference project.
