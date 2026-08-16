# proj-gamma
<!-- v1 — 2026-04-23 23:45 UTC -->

## Purpose
Server-side configuration — Nginx configs and deployment scripts.

## Contents
- `config.txt` — annotated excerpt of the current Nginx configuration and related deployment notes.

## How to use
Operational reference. Consult when touching infrastructure or debugging request-routing behavior.

## Gotchas
- Configs are environment-specific (hostnames, paths, certificate names). Do not copy verbatim to other hosts — adapt values per target.

State + mutable context: see CHECKPOINT.md.
