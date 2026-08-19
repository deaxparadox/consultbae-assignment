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
- Task 2: built the "Skill Auto-Tagging" n8n flow directly in the browser UI (self-hosted n8n via
  Docker, `n8n-nodes-sqlite3` community node) — manual trigger + webhook trigger → SQLite read
  (guarded query) → OpenAI (gpt-4o-mini) classification → trim/edit fields → SQLite parameterized
  update. Verified end-to-end against the real `consultbae.db`: all 56 people with skills got
  tagged, 0 remaining untagged with skills afterward, every returned tag matched one of the 5
  known categories. Root-caused a real bug in the community SQLite node while building it: it
  requires Postgres-style `$1`/`$2` placeholders (not `?`) with parameters bound as an actual array
  expression, not a comma-joined string (a string breaks because `skill_tags` values themselves
  contain commas) — found by reading the installed node's source inside the container, not
  guessed. Flow exported to `n8n/skill-tagging-flow.json` (contains only credential name/ID
  references, no secrets — verified before committing).
- Task 3: built the Streamlit audio app (`audio_app/app.py`, `audio_app/audio_metrics.py`) —
  Submit view (name/phone + `st.audio_input()` record or file upload) writes a `people` row
  (matched/created via the same phone-normalization logic as Task 1) and a `submissions` row;
  All Submissions view lists every submission with playback and its properties table. Metric
  ownership split per ADR 0001: pydub owns duration/sample rate/bitrate, librosa owns loudness
  (frame-based RMS → dB). Hit and fixed a real environment issue: Python 3.13 removed the stdlib
  `audioop` module pydub depends on — added the official `audioop-lts` backport rather than
  downgrading Python or patching around it. Verified end-to-end via browser automation against the
  running app (upload path): submitted a synthetic test WAV, confirmed extracted metrics matched a
  local sanity check exactly, confirmed the listing view and audio playback both work; test
  artifacts then removed from the DB so it stays in the clean Task 1+2 state for the real demo.
