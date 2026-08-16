# proj-relevant-2
<!-- v1 — 2026-04-23 23:45 UTC -->

## Purpose
Q2 sales figures for the same company, broken out by region and product.

## Contents
- `sales_q2.csv` — quarterly sales rows. Same 4-column schema as `proj-relevant-1/sales_q1.csv`.
- `README.txt` — one-line pointer to the CSV.

## How to use
Identical loading pattern to Q1: `csv.DictReader`, then coerce `units_sold` → `int`, `revenue_usd` → `float`.

## Gotchas
- Q2 rows are independent of Q1 rows. Do NOT deduplicate by `(region, product)` when combining — the same region/product pair is expected to appear in both quarters with different values.
- Revenue is already in USD.

State + mutable context: see CHECKPOINT.md.
