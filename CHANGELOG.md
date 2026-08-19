# Changelog

## Unreleased
- Set up repo (GitHub `deaxparadox/consultbae-assignment`, public), `.gitignore`, initial commit of
  source CSVs.
- Logged all 5 assignment tasks in `TODO.md`.
- Wrote ADR 0001 (stack & architecture) and one spec per task (`docs/specs/001`–`005`).
- Task 1: built `ingest/ingest.py` — merges the 3 source CSVs into `consultbae.db` via tiered
  entity resolution (email → phone → name-validator). Verified against real data: 102 rows
  processed into 61 people, 41 merges, 1 correctly-flagged name-mismatch case, 3 malformed/blank
  rows detected and skipped (source2 blank row + shifted-column row, source3 embedded duplicate
  header). Found and handled a design gap not anticipated in ADR 0001: `gig_rate` mixes hourly and
  monthly units with no conversion rule given — added `gig_rate_unit` column instead of silently
  guessing a conversion (see ADR 0001 Amendments).
