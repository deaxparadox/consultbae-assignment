# ADR 0001: Stack and Architecture for the ConsultBae Take-Home Assignment

## Status
Accepted

## Context
The assignment requires merging 3 messy CSV sources into one database (Task 1), building one
no-code automation against that data (Task 2), a mini audio-collection web app writing into the
same database (Task 3), a data-issues report generated from real pipeline output (Task 4), and a
one-page scaling analysis (Task 5). All 5 tasks share one database and must run together for a
single demo video, so the cross-task integration choices below were made together, not per task.

These decisions were made in an earlier design pass (web research + adversarial review, cited
inline in the original design notes) before implementation started. Recorded here as the binding
architecture reference; per-task specs reference this ADR rather than re-deriving these calls.

## Amendments (found during implementation)
- **`gig_rate_unit` column added** to `people` (nullable text, `hourly`/`monthly`). Not anticipated
  in the original design: source2's `rate` field mixes per-hour (`"1415/hr"`) and per-month
  (`"15k/month"`) values with no conversion rule given anywhere in the source data or prior design.
  Converting between them silently would require guessing a working-hours-per-month assumption not
  present in the data — instead `gig_rate_normalized` stores the numeric amount in its native unit
  and `gig_rate_unit` records which unit that is, so nothing is silently misrepresented. Logged as a
  judgment call in `DATA_ISSUES.md`, not treated as a design gap to silently patch around.

## Decisions

**Database: SQLite**, file-based, at project root, shared by Task 1 (writer), Task 2 (reader/writer
via n8n), and Task 3 (writer). Chosen for zero setup and because the schema is designed as plain
relational tables with no SQLite-specific features (see Task 5 doc — migrating to Postgres later is
a connection-string swap, not a redesign).
- `PRAGMA journal_mode=WAL;` and `PRAGMA busy_timeout=5000;` set on every connection (Task 1 script,
  Task 3 app; n8n's SQLite node too if it exposes the option) — WAL allows concurrent readers/writers,
  busy_timeout absorbs any rare simultaneous-write collision instead of erroring during the demo.

**Schema** — 3 tables:
- `people` (canonical merged person): `person_id` PK, `full_name`, `email`, `phone_normalized`,
  `phone_raw`, `city_raw` (kept as-is, inconsistency logged in Task 4 report rather than normalized),
  `skill_tags` (written by Task 2's LLM step), `skills_raw` (union of source1+source2 skills, feeds
  Task 2), `experience_years`, `current_ctc_normalized`/`current_ctc_raw`,
  `applied_date_normalized`/`applied_date_raw`, `gig_rate_normalized`/`gig_rate_raw`/`gig_rate_unit` (see Amendments),
  `gig_status_normalized`/`gig_status_raw`, `verified`, `projects_completed`. All flattened fields
  nullable since not every person appears in every source.
- `source_records` (provenance): `record_id` PK, `person_id` FK, `source_file`, `raw_row_json`,
  `match_tier` (email/phone/none), `match_confidence` (high/flagged) — queried directly by Task 4 as
  its evidence source for flagged/low-confidence merges, not written from memory.
- `submissions` (Task 3 writes here): `submission_id` PK, `person_id` FK, `audio_path`,
  `duration_sec`, `sample_rate_hz`, `bitrate_kbps`, `loudness_db`, `created_at`.

**Entity resolution: tiered matching**, priority order — Tier 1 email exact match (case-insensitive)
→ Tier 2 phone match (normalized to last 10 digits, strips +91/leading 0/hyphens — only field common
to all 3 sources) → Tier 3 name check, used only as a validator on top of tier 1/2, never standalone.
Email or phone match + names agree → auto-merge. Email or phone match + names disagree → flag,
don't auto-merge. No email/phone match → separate record even if names look similar (name-only
matching rejected as unreliable). Rationale and edge cases: see docs/specs/001.

**Task 2 platform: self-hosted n8n via Docker**, not the cloud trial — verified the cloud trial
cannot access SQLite (no official SQLite node; the community node `n8n-nodes-sqlite3` needs
self-hosting). Docker run needs a second bind mount beyond the default n8n_data volume, since
containers don't see the host filesystem by default:
```
docker run -it --rm --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v ~/consultbae-assignment:/data \
  docker.n8n.io/n8nio/n8n
```
Inside n8n's SQLite node config, the DB path is the container-internal `/data/consultbae.db`, not
the host path. Task 3 (Streamlit) is not containerized — runs on host, uses the normal relative
path `./consultbae.db`.

**Task 2 flow: LLM skill auto-tagging**, OpenAI node (built into n8n, uses existing API key), 5
categories (automation-heavy, web dev, data, backend/API, scraping/QA — derived from the actual 16
unique skill values across source1+source2), multi-tag allowed. Read query is guarded to exclude
Task 3's audio-only submitters (who have no skills data):
`SELECT person_id, skills_raw FROM people WHERE (skill_tags IS NULL OR skill_tags = '') AND skills_raw IS NOT NULL AND skills_raw != ''`.
Write: `UPDATE people SET skill_tags = ? WHERE person_id = ?`.

**Task 3 audio libraries — strict lane separation** (different libraries can disagree on the same
metric, so each metric has exactly one owner):
- `pydub` (ffmpeg-backed) owns `duration_sec`, `sample_rate_hz`, `bitrate_kbps`. For WAV, bitrate is
  computed explicitly (`sample_rate × bit_depth × channels`), not trusted from metadata.
- `librosa` owns `loudness_db` only, via frame-based RMS (`librosa.feature.rms` → `amplitude_to_db`),
  not pydub's whole-file dBFS.
- Recording widget: Streamlit's native `st.audio_input()` (no third-party component), with
  `st.file_uploader()` as the upload alternative. `audio-recorder-streamlit` is the fallback if
  `st.audio_input()` proves flaky.
- Deployment: run locally during the demo recording (assignment explicitly allows this) — no
  deployment risk under time pressure. Cloud deployment is optional stretch only.

**Build/demo sequencing (fixed):** Task 1 (ingestion) → Task 2 (n8n, needs populated DB) → Task 3
(app, only needs schema to exist, but demoed last for narrative clarity) → Task 4 (report, from real
pipeline output) → Task 5 (docs only, no code).

## Consequences
- All 3 runtime components (ingestion script, n8n, Streamlit app) depend on one shared SQLite file
  and must agree on its path via the container/host mount mapping above — getting this wrong is the
  most likely source of a demo-day failure, so it's called out explicitly rather than left implicit.
- `source_records` exists specifically to make Task 4 evidence-based; if Task 4 is ever written
  without querying it, that's a process violation of this ADR, not a stylistic choice.
- Postgres/object-storage/human-review-queue migrations described in Task 5 are explicitly NOT
  implemented now — they're the documented answer to "what breaks at scale," not current scope.
