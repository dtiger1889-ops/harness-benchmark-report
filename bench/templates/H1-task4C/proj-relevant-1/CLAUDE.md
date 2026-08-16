# proj-relevant-1
<!-- v1 — 2026-04-23 23:45 UTC -->

## Purpose
Q1 sales figures for the company, broken out by region and product.

## Contents
- `sales_q1.csv` — quarterly sales rows. Schema: `region, product, units_sold, revenue_usd`.
- `README.txt` — one-line pointer to the CSV.

## How to use
Load `sales_q1.csv` via `csv.DictReader`. Coerce `units_sold` to `int` and `revenue_usd` to `float` — the file is stored as plain strings.

## Gotchas
- The header row matches `proj-relevant-2/sales_q2.csv` exactly. Safe to concatenate the two CSVs without header reconciliation.
- Revenue is already in USD — do not apply currency conversion.

State + mutable context: see CHECKPOINT.md.
