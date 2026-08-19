# Spec 004: Task 4 — Data Issues Report

**Branch:** `main` (base: `main`).

## What's being built
`DATA_ISSUES.md` at repo root: a markdown table (`Issue | Where Found | Example | Resolution`), one
row per issue category, plus short prose for judgment calls that don't fit a table cell (e.g. city
casing normalization decision).

## Design rationale
- Every row must trace to actual output from Task 1's real ingestion run — row counts, flagged-match
  examples, malformed-row counts — not written from memory or from the design-pass scratchpads.
- Flagged/low-confidence entity-resolution cases are pulled directly from `source_records`:
  `SELECT sr.source_file, sr.raw_row_json, sr.match_tier, p.full_name, p.phone_normalized FROM source_records sr JOIN people p ON sr.person_id = p.person_id WHERE sr.match_confidence = 'flagged'`.
  This table exists specifically so this report is evidence-based (ADR 0001) — if this query isn't
  run, the report shouldn't claim specific flagged examples.
- A full systematic scan (not just the issues eyeballed during design) must run against the real
  ingestion output before this report is finalized — covers things like whitespace-only names,
  intra-file duplicate rows, out-of-range experience/CTC values, and any phone with an unexpected
  digit count beyond the one example already found.

## Implementation
- Run the evidence queries above (and the full scan) against the real `consultbae.db` produced by
  Task 1's script.
- Write `DATA_ISSUES.md` from that output.
- Link (don't duplicate) from `README.md`'s setup/report section.

## Out of scope here
Fixing any newly-discovered issue that Task 1 didn't already handle — if the full scan turns up
something Task 1's script doesn't cover, that's a new finding to flag to the user before deciding
whether to patch Task 1 or just log it as a known limitation (matches CLAUDE.md's root-cause rule —
no silently patching Task 1 after the fact without surfacing it first).
