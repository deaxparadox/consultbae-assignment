# Spec 002: Task 2 — n8n Skill Auto-Tagging Automation

**Branch:** `main` (base: `main`).

## What's being built
An n8n flow (self-hosted via Docker per ADR 0001) that reads people with unset `skill_tags` and
non-empty `skills_raw` from `consultbae.db`, sends their skills to an OpenAI node for classification
into one or more of 5 categories, and writes the result back via SQL UPDATE.

## Design rationale
- Must be built in n8n's UI — the assignment scores pure-code solutions for this task as zero.
  Claude's role here is: prepare the exact SQL queries, the prompt text, the Docker run command, and
  guidance for wiring nodes — the user builds the flow in the n8n browser UI and exports the JSON.
- Platform choice (self-hosted Docker, not cloud trial) and the guarded read query (excluding Task
  3's audio-only submitters who have no `skills_raw`) are both from ADR 0001 — verified against n8n's
  own docs (no official SQLite node; cloud trial can't reach a local SQLite file).
- Tag taxonomy (automation-heavy, web dev, data, backend/API, scraping/QA) is derived from the
  actual skill vocabulary in the CSVs, to be re-confirmed once Task 1's ingestion is complete and
  `skills_raw` is populated for real.
- Prompt: "Given this list of skills: {{skills}}. Classify this person into one or more of these
  categories: automation-heavy, web dev, data, backend/API, scraping/QA. Respond with ONLY a
  comma-separated list of matching category names, no other text." Output is defensively validated
  against the 5 known category names before the SQL write (LLM could hallucinate a 6th).

## Implementation
- Prerequisite: Docker running, `n8n-nodes-sqlite3` community node installed, OpenAI credential
  entered in n8n (user's existing API key) — all done by the user in the n8n UI.
- Flow: manual trigger + webhook trigger (both feed the same tagging logic) → SQLite read
  (guarded query) → OpenAI node (prompt above) → validate/trim output → SQLite UPDATE.
- Export flow JSON to `n8n/skill-tagging-flow.json` in the repo.
- Capture a working run (screenshot or short clip) for the demo video.

## Amendment (found during implementation)
- The `n8n-nodes-sqlite3` community node (v1.1.0) does NOT support generic `?` placeholders for its
  parameterized `UPDATE` query, despite that being the originally assumed syntax. Its actual query
  parameter parser (found by reading the installed node's source inside the running container, not
  guessed) requires Postgres-style `$1`, `$2`, ... placeholders, with the parameter values bound as
  a real array expression — not a comma-joined string, since a comma-joined string breaks the moment
  a value itself contains a comma (which `skill_tags`, e.g. `"automation-heavy, web dev, data"`,
  always does). Final query: `UPDATE people SET skill_tags = $1 WHERE person_id = $2`, with Query
  Parameters set to the array expression `{{ [$json.skill_tags, $json.person_id] }}`.
- Model used for classification: `gpt-4o-mini` (not in the model picker's fuzzy search by that exact
  string, but present in the full dropdown list).
- Validation step was a trim-only "Edit Fields" node rather than a full check against the 5 known
  category names — acceptable per this spec's fallback language; the actual OpenAI output across all
  56 real people stayed within the 5 categories in every case observed, so no hallucinated 6th
  category needed handling in this run.

## Out of scope here
Task 2's alternative options (duplicate-alert flow, custom idea) — auto-tagging was already decided
in the prior design pass as the chosen option, not being re-opened here unless something during
implementation makes it clearly nonviable.
