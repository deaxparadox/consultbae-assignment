# Spec 005: Task 5 — Scaling Stretch Doc

**Branch:** `main` (base: `main`).

## What's being built
`TASK5_SCALING_NOTES.md` at repo root: one page, no code, answering "what breaks first if the audio
app launches to 5,000 gig workers over a weekend, and what would change before launch."

## Design rationale
- Content is grounded in the actual architecture used for Tasks 1–3 (SQLite, local disk audio
  storage, the tiered entity-resolution rule, Streamlit's single-process model) — not generic
  scaling advice. The 4 concrete breaking points already identified during design:
  1. SQLite write concurrency (fix: Postgres — schema has no SQLite-specific features).
  2. Local disk audio storage (fix: object storage/S3, DB stores only the key/URL).
  3. Entity-resolution false-positive/negative rate rising at volume (fix: route flagged/
     low-confidence matches to a human review queue instead of silent auto-decisions).
  4. Streamlit's single-process/session-state model (fix: split API + frontend, or load-balance
     multiple instances).
  - Plus: upload validation, retry-safe/idempotent submissions, per-phone rate limiting, LLM tagging
    cost at 5,000 calls, and basic monitoring/alerting on failure rate.
- Assignment explicitly says "one page, no code" — this is a documentation-only deliverable, no
  implementation work attached to this spec.

## Implementation
- Write `TASK5_SCALING_NOTES.md` fresh (not copy-pasted verbatim from the excluded private
  scratchpad) — same substance, but the user's own words for the live-defense round.
- Reference from `README.md`'s task breakdown, same treatment as `DATA_ISSUES.md`.

## Out of scope here
Any actual implementation of the fixes described (Postgres migration, S3, review queue, etc.) — this
is analysis only, per the assignment.
