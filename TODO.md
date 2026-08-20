# TODO

Tracking file for ConsultBae AI Automation take-home assignment. Deadline: 2026-08-21, ~10:52 AM IST.

## Setup
- [x] Create public GitHub repo `deaxparadox/consultbae-assignment`, push initial commit (CSVs + .gitignore). CLAUDE.md and docs/claude-web-design/ excluded per user decision.
- [x] ADR 0001: stack & architecture decisions (docs/adr/0001-stack-and-architecture.md)
- [x] Spec + implement Task 1 — Merge pipeline (docs/specs/001-task1-merge-pipeline.md) — 61 people from 102 rows, 41 merges, 1 flagged, 3 malformed rows skipped. See ingest/ingestion_log.txt for the real run output.
- [x] Spec + implement Task 2 — n8n automation (docs/specs/002-task2-n8n-automation.md) — built via browser automation against the real n8n UI; 56/61 people tagged in the live DB, flow exported to n8n/skill-tagging-flow.json.
- [x] Spec + implement Task 3 — Audio collection app (docs/specs/003-task3-audio-app.md) — verified end-to-end via browser automation (upload path), DB reset to clean state (61 people, 0 submissions) after test.
- [x] Spec + implement Task 4 — Data issues report (docs/specs/004-task4-data-issues-report.md) — DATA_ISSUES.md written from real ingestion output + source_records queries; found and fixed a real Task 1 bug in the process.
- [x] Spec + implement Task 5 — Scaling stretch doc (docs/specs/005-task5-scaling-doc.md) — TASK5_SCALING_NOTES.md, grounded in the real ambiguous-match cases found during Task 4.
- [x] Submission package: README.md written (setup steps, data issues/scaling doc links, draft stuck log — **flagged for your review/personalization before submitting**, see README's stuck log note). CHANGELOG and FLOWS.md kept current throughout.
- [x] Docker Compose setup (`docker-compose.yml`, `Dockerfile`, `.dockerignore`) to launch n8n + the audio app together with one command, reusing the existing `n8n_data` volume — verified nothing (owner account, workflow, community node, credentials) was lost switching the running n8n container over to compose.
- [ ] User: screen recording (≤6 min)
- [ ] User: reply to assignment email with repo + video links

## Notes
- Sequencing is fixed per architecture doc: Task 1 → Task 2 → Task 3 → Task 4 → Task 5.
- Task 2 must be built in n8n's UI (pure-code scores zero) — Claude prepares flow design/queries, user builds and exports the flow JSON.
- Stuck log must be genuinely user-authored (graded specifically on authenticity).
