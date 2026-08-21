# ConsultBae — AI Automation Take-Home Assignment

Three messy CSV exports from three different systems, merged into one SQLite database. An n8n flow
reads people out of it, gets OpenAI to classify their skills, and writes the tags back. A small
Streamlit app lets a gig worker submit a name, phone number, and an audio recording, pulling out
duration/sample rate/bitrate/loudness automatically. All three pieces share the same database.

Why I made the choices I did is written up in `docs/adr/0001-stack-and-architecture.md`, and each
task has its own short spec under `docs/specs/` if you want the reasoning behind a specific piece.

## Getting it running

I built this two ways — pick whichever is easier for you.

### The easy way: Docker Compose

```bash
docker volume create n8n_data   # only needed the very first time
docker compose up -d --build
```

That brings up n8n at `localhost:5678` and the Streamlit app at `localhost:8501`, both pointed at
the same database, which lives in its own `data/` folder rather than the repo root — each service
only gets that one folder mounted in, not the whole repo. It's a folder rather than a single file
on purpose: single-file bind mounts are unreliable on Docker Desktop for Windows, mounting a
directory isn't. n8n keeps its own state (owner login, credentials, the installed community node,
the workflow itself) in a separate named volume, so restarting or rebuilding doesn't wipe any of
that out.

Before any of that works you need the database to actually exist:

```bash
docker compose run --rm ingest
```

That one *does* get the whole repo mounted — it needs to read the source CSVs and write the
resulting database back to the repo root, and it only ever runs as a one-off you trigger yourself,
never as part of `up`.

I kept this out of the normal startup on purpose — it rebuilds `consultbae.db` from scratch every
time, and if you'd already run the n8n tagging step, that would wipe the tags back out. Run it once
up front.

Then in n8n itself: set up the owner account (only asks once), go to Settings → Community Nodes and
install `n8n-nodes-sqlite3`, and add two credentials — an OpenAI one with your own key, and a SQLite
one pointed at `/data/consultbae.db` (that's the path *inside* the container; the bind mount is what
makes it line up with the real file on your machine). After that, import
`n8n/skill-tagging-flow.json` from the Workflows screen, swap in your own two credentials on the
nodes that need them (an exported flow only remembers credential names, not the actual secrets),
and hit the manual trigger to run it.

### The other way: everything on your own machine, no Docker for the Python bits

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # you'll need ffmpeg installed separately for this
.venv/bin/python ingest/ingest.py
```

That last command is Task 1 — it builds `data/consultbae.db` from the three CSVs and prints a
summary of what it did (also saved to `ingest/ingestion_log.txt`, which is where the numbers in
`DATA_ISSUES.md` actually came from).

n8n still needs Docker either way:

```bash
docker run -d --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -v "$(pwd)/data":/data \
  docker.n8n.io/n8nio/n8n
```

then the same setup steps as above. And the audio app:

```bash
.venv/bin/streamlit run audio_app/app.py
```

which opens at `localhost:8501` — one tab to submit a recording (record it right in the browser or
upload a file), another that lists everything submitted so far with a play button and the extracted
properties next to it.

## The data issues

`DATA_ISSUES.md` has the full list of what was wrong with the three source files and what I did
about each one. Every number in there came from actually running the pipeline and querying the
resulting database — nothing in it is from memory.

## If this had to handle 5,000 people in a weekend

`TASK5_SCALING_NOTES.md` — what I think would actually break first, based on how this specific
system is built rather than generic scaling advice.

## Where I actually got stuck

Three things came up while building this that took real digging, not just "look it up and move on."

**n8n's SQLite node wanted a completely different parameter syntax than I expected.** I wrote the
update query the normal way — `UPDATE people SET skill_tags = ? WHERE person_id = ?` with plain `?`
placeholders — and it just failed with "Too few parameter values were provided," no useful hint
beyond that. I didn't have web access from where I was working, so instead of guessing at syntax
variations I opened a shell into the running container and read the actual source of the installed
`n8n-nodes-sqlite3` package. Turned out it parses placeholders like Postgres does — `$1`, `$2`, and
so on — and it splits its parameter list on commas unless you hand it a real array, which breaks
the moment one of your values contains a comma. Mine did: `skill_tags` looks like
`"automation-heavy, web dev, data"`. So two things had to change together — the placeholders, and
passing the parameters as an actual array expression rather than a joined string. Details are in
`docs/specs/002-task2-n8n-automation.md` if you want the exact before/after.

**pydub wouldn't even import.** `ModuleNotFoundError: No module named 'audioop'` — Python 3.13
dropped that module from the standard library, and pydub depends on it unconditionally. Downgrading
Python felt like the wrong fix since it'd ripple into everything else, and I'd already deliberately
picked pydub for consistent duration/sample-rate/bitrate extraction, so swapping libraries wasn't
appealing either. There's an actual maintained backport for exactly this situation —
`audioop-lts` — so I added that instead, conditioned on Python version so it only installs where
it's actually needed.

**A real bug in my own merge logic, and I only found it because Task 4 forced a proper scan.**
Task 4 isn't just "write down the issues you already noticed" — it wants a real pass over the
finished database. Doing that turned up five people whose email or phone number was sitting there
as `NULL` in the database, even though that exact value had clearly been used to match other rows
against them during ingestion. The bug: when a new person gets created, I was only inserting their
name — email and phone were supposed to get filled in afterward by whichever source file processed
next, and two of my three per-source update steps forgot to include those columns. I fixed it so
both get written the moment the row is created, reran the whole pipeline, and checked again to
confirm there weren't any more like it.
