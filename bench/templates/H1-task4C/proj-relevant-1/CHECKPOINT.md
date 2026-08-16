Last updated: 2026-04-23 23:45 UTC

## Status
Static reference data. No active work in progress.

## Goal
Preserve Q1 sales figures as an immutable, readable source for downstream reporting.

## Key decisions
- CSV chosen over Parquet/SQLite so the file is readable without dependencies.
- Revenue stored in raw USD with no rounding — consumers decide precision.

## Open threads
- None.

## Files that matter
- `sales_q1.csv` — the data. Schema is stable.
- `README.txt` — short pointer for consumers.

## Next step
None — reference project.
