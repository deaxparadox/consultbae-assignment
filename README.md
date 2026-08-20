# ConsultBae — AI Automation Take-Home Assignment

Merges 3 messy CSV sources into one SQLite database, auto-tags each person's skill category via an
n8n + OpenAI flow, and collects audio submissions through a small Streamlit app — all sharing the
same database. See `docs/adr/0001-stack-and-architecture.md` for the full architecture rationale
and `docs/specs/` for one spec per task.

## Setup

### Option A — one command (Docker Compose)
```bash
docker volume create n8n_data   # first time only, if it doesn't already exist
docker compose up -d --build
```
Brings up both n8n (`http://localhost:5678`) and the Streamlit audio app (`http://localhost:8501`)
together, sharing this repo via bind mount so both see the same `consultbae.db`. n8n's own data
(owner account, credentials, installed community node, workflows) persists in the external
`n8n_data` named volume across restarts/rebuilds.

Build the database first (one-off, not part of the normal `up` — it drops and recreates
`consultbae.db`, which would wipe any `skill_tags` already written by Task 2):
```bash
docker compose run --rm audio_app python ingest/ingest.py
```
Then in the n8n UI: create an owner account (first run only), Settings → Community Nodes → install
`n8n-nodes-sqlite3`, add an OpenAI credential and a SQLite credential (Database File Path
`/data/consultbae.db` — that's the container path; the bind mount maps it to the repo root on the
host), import `n8n/skill-tagging-flow.json` (reassigning both credentials to your own — exported
flows only carry credential name/ID references, not the credentials themselves), and run it via
the manual trigger.

### Option B — run each piece directly on the host
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # requires ffmpeg installed as a system dependency
.venv/bin/python ingest/ingest.py           # Task 1 — builds consultbae.db, logs to ingest/ingestion_log.txt
```
Task 2 (n8n) — same as Option A's n8n steps, but launched standalone instead of via compose:
```bash
docker run -d --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v "$(pwd)":/data \
  docker.n8n.io/n8nio/n8n
```
Task 3 (audio app):
```bash
.venv/bin/streamlit run audio_app/app.py
```
Opens at `http://localhost:8501`. "Submit" records/uploads audio and writes a person + submission;
"All Submissions" lists everything with playback and extracted properties (duration, sample rate,
bitrate, loudness).

## Data issues report
See [`DATA_ISSUES.md`](DATA_ISSUES.md) — every problem found in the 3 source files and what the
ingestion script does about it, generated from the actual pipeline's output.

## Scaling stretch (Task 5)
See [`TASK5_SCALING_NOTES.md`](TASK5_SCALING_NOTES.md).

## Stuck log

> Draft — three things genuinely came up while building this that took real debugging, not
> guesswork. Read through these (and the corresponding ADR/spec amendment notes they reference)
> before the live call so you can speak to them in your own words — this section is meant to be
> reviewed and personalized, not submitted as-is.

**1. The n8n community SQLite node's parameter syntax wasn't what the docs/prior design assumed.**
The plan was a standard parameterized `UPDATE people SET skill_tags = ? WHERE person_id = ?` with
generic `?` placeholders. It failed with "Too few parameter values were provided." There's no web
access from inside the environment building this, so instead of guessing at syntax variants, the
fix came from reading the installed `n8n-nodes-sqlite3` package's actual source file inside the
running Docker container (`docker exec n8n cat .../executeQuery.operation.js`). That showed it
parses placeholders with a Postgres-style `/\$(\d+)/g` regex — so it needs `$1`, `$2`, ... — and
that its parameter-splitting logic assumes a comma-joined string unless given a real array, which
breaks the moment a parameter value itself contains a comma (which `skill_tags`, e.g.
`"automation-heavy, web dev, data"`, always does). Both fixes were needed together: `$1`/`$2`
placeholders, and an actual array expression (`{{ [$json.skill_tags, $json.person_id] }}`) instead
of a string. See `docs/specs/002-task2-n8n-automation.md`'s Amendment section.

**2. `pydub` wouldn't import at all — Python 3.13 removed a module it depends on.**
`ModuleNotFoundError: No module named 'audioop'`. Python 3.13 removed the stdlib `audioop` module
(PEP 594); `pydub` imports it unconditionally. Rejected downgrading the Python version (too blunt,
affects everything else) and rejected switching away from pydub (it was already the deliberate
choice for consistent duration/sample-rate/bitrate extraction across formats). The actual fix is
the `audioop-lts` package — a backport published specifically for this removal — added as a
conditional dependency (`audioop-lts; python_version >= "3.13"`). See
`docs/specs/003-task3-audio-app.md`'s Amendment section.

**3. A real bug in the merge pipeline itself, only caught by Task 4's systematic scan.**
Task 4 requires an exhaustive scan of the actual database, not just the issues already known from
looking at the CSVs by eye. That scan turned up 5 people whose `email` or `phone_normalized` column
was `NULL` in the database despite that exact value having been used, in memory, to match other
rows against them moments earlier during ingestion. Root cause: the function that creates a brand
new person row only inserted `full_name` — email/phone were meant to get backfilled by each
source file's later `UPDATE` statement, and two of the three per-source `UPDATE`s were missing
those columns. Fixed by writing both columns directly at row-creation time instead, then re-ran the
full pipeline and re-verified the scan found zero remaining cases. This is exactly the kind of
"caught in a full scan, not caught by eyeballing" issue Task 4 is meant to surface.
