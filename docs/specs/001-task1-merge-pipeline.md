# Spec 001: Task 1 — Merge Pipeline

**Branch:** `main` (base: `main`) — committing directly per-task, no feature branches, per user's
time-pressure call; each task lands as its own commit(s) on `main`.

## What's being built
A Python ingestion script that reads the 3 source CSVs (`docs/assignment-files/source1_naukri_applicants.csv`,
`source2_gig_workers.csv`, `source3_cbnexus_contacts.csv`), creates `consultbae.db` (SQLite) at the
project root with the schema from ADR 0001, and merges the same person appearing across files into
one `people` row using the tiered entity-resolution rule.

## Design rationale (verified against the CSVs)
- No common ID field across the 3 sources — confirmed by header inspection.
- Tiered matching (email → phone → name-as-validator-only) per ADR 0001: chosen because email/phone
  are the only fields with enough uniqueness to merge safely; name-only matching is rejected because
  the data has repeated common names (2x Priya, 2x Arjun) that would cause false merges.
- Normalization rules (all per ADR 0001 / prior design pass, to be re-verified against the actual
  files during implementation, not assumed):
  - Phone: strip `+91`, leading `0`, hyphens/spaces → last 10 digits.
  - CTC: `< 100` → lakhs, multiply ×100,000; `≥ 100` → already rupees. Store both raw and normalized.
  - Date: 3+ formats present (slash MM/DD, hyphen DD-MM, ISO, text-month) → normalize all to ISO
    `YYYY-MM-DD`, keep raw.
  - `verified`: Y/yes → true, N/No → false, blank → null (explicitly "unknown", not false).
  - City: kept as `city_raw`, not normalized — inconsistency logged in Task 4 instead.
- Known malformed-row issues to handle explicitly (skip + log, not silently drop):
  source2 has a fully blank row and a row with shifted/rotated columns; source3 has a repeated
  header row embedded as a data row.
- Every write is provenance-tracked into `source_records` (raw row JSON + match tier/confidence) —
  this table is Task 4's evidence source, not optional bookkeeping.

## Implementation
- `ingest/` directory: `ingest.py` (entry point), normalization helper functions, matching logic.
- `requirements.txt`: `pandas`, stdlib `sqlite3`.
- Script is idempotent-safe to note (rerun behavior) but idempotency itself is out of scope —
  demo runs it once against a fresh DB.
- Validate at the end: row counts in vs. unique people out, spot-check a couple of flagged/merged
  cases against the source files.

## Out of scope here
Task 2/3/4/5 work — those are separate specs, sequenced after this one per ADR 0001.
