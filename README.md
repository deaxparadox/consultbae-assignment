# ConsultBae — AI Automation Take-Home Assignment

Merges 3 messy CSV sources into one SQLite database, auto-tags each person's skill category via an
n8n + OpenAI flow, and collects audio submissions through a small Streamlit app — all sharing the
same database. See `docs/adr/0001-stack-and-architecture.md` for the full architecture rationale
and `docs/specs/` for one spec per task.

## Setup

### 1. Python environment
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
Requires `ffmpeg` installed as a system dependency (used by `pydub` for audio decoding).

### 2. Task 1 — build the database
```bash
.venv/bin/python ingest/ingest.py
```
Reads the 3 CSVs in `docs/assignment-files/`, creates `consultbae.db` at the repo root, and prints
a summary (rows processed, people created/merged, flagged cases, skipped malformed rows) — also
written to `ingest/ingestion_log.txt`. This is the evidence source for `DATA_ISSUES.md`.

### 3. Task 2 — n8n skill auto-tagging
```bash
docker run -d --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v "$(pwd)":/data \
  docker.n8n.io/n8nio/n8n
```
Then in the browser at `http://localhost:5678`:
1. Create an owner account (first-run only, local instance).
2. Settings → Community Nodes → install `n8n-nodes-sqlite3`.
3. Add credentials:
   - **OpenAI** — your own API key.
   - **SQLite** — Database File Path: `/data/consultbae.db` (this is the container-internal path;
     the bind mount above maps it to the repo root on the host).
4. Import `n8n/skill-tagging-flow.json` (Workflows → Import from File), or rebuild it by hand per
   `docs/specs/002-task2-n8n-automation.md` — reassign both credentials to your own if importing,
   since exported flows only carry credential name/ID references, not the credentials themselves.
5. Run it via the manual trigger. It reads people with skills but no `skill_tags` yet, classifies
   them via OpenAI, and writes the result back.

### 4. Task 3 — audio collection app
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
