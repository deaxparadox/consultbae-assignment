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
- Bugfix (found during Task 4's systematic scan): `ingest/ingest.py`'s `_create_person()` only
  inserted `full_name` on row creation, leaving `email`/`phone_normalized` to be filled in later by
  each source-specific `UPDATE` — two of the three per-source `UPDATE`s were missing those columns,
  so people first created from source2 or source3 alone had `NULL` email/phone in storage despite
  that value being used in memory to match them. Fixed by writing both columns at creation time.
  Re-ran the full ingestion pipeline (61 people, same merge structure) and re-verified the scan
  found zero remaining cases. Re-ran Task 2's n8n flow afterward since regenerating the DB wiped
  its `skill_tags` writes — reconfirmed 56/61 tagged, 0 remaining untagged with skills.
- Task 4: wrote `DATA_ISSUES.md` from real pipeline output — every row traces to
  `ingest/ingestion_log.txt` or a direct query against `consultbae.db`/`source_records`. Covers 3
  malformed/blank rows, phone/email/date/CTC/verified format inconsistencies and their
  normalization rules, 2 deliberate non-normalization judgment calls (city casing, gig-rate units),
  the one real flagged name-mismatch case, same-name-different-people and
  split-across-sources-with-no-anchor as documented known limitations, and the Task 1 bug found and
  fixed above. Full scan performed: zero malformed phones/emails, zero out-of-range
  experience/CTC/projects values, zero date-parse failures, beyond what's listed in the table.
- Task 5: wrote `TASK5_SCALING_NOTES.md` (one page, no code) — SQLite write concurrency, local
  disk audio storage, Streamlit's single-process model, and entity-resolution degrading at volume
  as the 4 things that break first at 5,000 workers. The entity-resolution point is grounded in
  real evidence from Task 4's scan (the actual un-merged same-name records and the
  split-across-sources case found in the 102-row test data), not hypothetical concern.
- Wrote `README.md`: setup steps for all 3 runtime pieces (ingestion script, n8n via Docker,
  Streamlit app), links to `DATA_ISSUES.md`/`TASK5_SCALING_NOTES.md`, and a draft stuck log
  covering the 3 real technical incidents hit while building this (n8n parameter syntax, Python
  3.13/audioop, the Task 1 email/phone persistence bug) — flagged as needing the user's own review
  and personalization before submission, since the assignment grades this section on authenticity.
- Added `docker-compose.yml` + `Dockerfile` + `.dockerignore` to launch n8n and the Streamlit app
  together with `docker compose up -d --build`. The n8n service reuses the existing external
  `n8n_data` named volume rather than a fresh one, so the already-built owner account, workflow,
  installed community node, and credentials aren't lost; the audio app bind-mounts the repo so it
  shares the same `consultbae.db` on the host. Verified by removing the standalone `n8n` container
  and bringing the stack up via compose: n8n showed a normal login screen (not first-run setup),
  and the "Skill Auto-Tagging" workflow, `n8n-nodes-sqlite3`, and both credentials all confirmed
  intact afterward. README updated with the one-command path as the primary setup option.
- Security fix (flagged by automated commit review, verified as real before fixing): the Compose
  setup's `Dockerfile` had no `.dockerignore` entry for `CLAUDE.md`/`docs/claude-web-design/`, so
  `COPY . .` baked both into the built image layer — confirmed via `docker run --entrypoint sh`
  against the already-built image, which showed both readable at `/app/CLAUDE.md` and
  `/app/docs/claude-web-design/*`. The runtime bind mounts (`.:/data`, `.:/app`) exposed them live
  too, independent of `.dockerignore` (which only affects build context, not volumes). Both
  directly undermined the earlier explicit decision to keep these out of the repo. Also found both
  services published ports on `0.0.0.0` rather than localhost, exposing the fully-unauthenticated
  Streamlit app (handles real names/phone numbers) to the local network, not just this machine.
  Fixed: added both paths (plus `.env`, preemptively) to `.dockerignore`; added shadow mounts
  (`/dev/null` over the file, an anonymous volume over the directory) in `docker-compose.yml` as a
  second line of defense against the runtime bind mount regardless of `.dockerignore`; changed both
  port mappings to `127.0.0.1:PORT:PORT`. Rebuilt the image with the old cached layer removed,
  verified both files are now empty/unreachable inside both containers, and confirmed the DB is
  still accessible and n8n's persisted state (login required, workflow, credentials) survived.
- Rewrote `README.md` in a plainer, first-person voice — same setup steps, report links, and stuck
  log content, just rephrased so it reads like the candidate wrote it rather than generated docs.
- Fixed a crash on Windows/Docker Desktop: `docker compose up` failed with "make mountpoint
  '/data/CLAUDE.md': file exists", caused by the previous shadow-mount fix (mounting the whole repo,
  then mounting `/dev/null` over specific paths inside it) — that pattern turned out to be fragile
  and platform-dependent, working on Linux but not on Windows' bind-mount handling. Root-cause fix:
  stopped mounting the whole repo into `n8n`/`audio_app` at all. Each now gets only the single
  file/directory it actually needs (`consultbae.db`; `audio_uploads/` for the audio app too) — which
  makes the shadow-mount trick unnecessary rather than just less broken. The full-repo mount moved to
  a new one-off `ingest` service (needs to read the CSVs and write the db), gated behind a Compose
  profile so it never runs as part of `up` — only via `docker compose run --rm ingest`. Verified: `up`
  no longer touches `ingest`, both long-running services still work end-to-end, and `CLAUDE.md`/
  `docs/claude-web-design` are now simply absent from their containers rather than shadowed-empty.
- Fixed `n8n/skill-tagging-flow.json`: it failed to import in n8n's UI with "The imported data does
  not contain valid workflow data ('nodes' and 'connections' are missing)". Root cause: the
  `n8n export:workflow` CLI command wrapped the workflow in a JSON array (`[{...}]`); the UI's
  "Import from file" only accepts a plain workflow object at the top level. Unwrapped it to a plain
  object and verified by importing it into the live local n8n instance — 6 nodes, 5 connections, no
  error — then deleted that test import without touching the real workflow.
- Fixed `ingest/ingest.py` raising `IsADirectoryError` on a fresh Windows clone. `consultbae.db`
  didn't exist yet, and Docker Desktop's bind-mount handling creates a placeholder directory (on
  both sides — inside the container and on the host) when a single-file mount targets a path that
  isn't there yet; this got triggered by running ingestion against `audio_app`'s now single-file
  mount (the pre-narrow-mount command) instead of the dedicated `ingest` service, which mounts the
  full repo. Added an explicit, actionable error in the script for this case instead of leaving a
  raw traceback — the user is about to record their demo, and a clear message beats a bare stack
  trace on camera. Verified on Linux by deliberately recreating the directory-instead-of-file
  condition and confirming both the new error message and normal operation afterward.
