# Task 5 — Scaling to 5,000 Gig Workers Over a Weekend

One page, no code. Grounded in the actual system built for Tasks 1–3, not generic scaling advice.

## What breaks first

**1. SQLite's single-writer lock**
Every audio submission in Task 3 does a person lookup and two writes (a `people` row if the
person is new, plus a `submissions` row). SQLite locks the whole file per write. At demo scale
(one person testing) this is invisible; at real weekend traffic — dozens of workers submitting in
the same few minutes, on top of Task 2's n8n flow potentially still running — writes start
queuing behind each other. First symptom is submissions taking longer than they should; under
sustained load that becomes visible failures/timeouts, not just slowness.
*Before launch:* migrate to Postgres. The schema (`people`, `source_records`, `submissions`) uses
no SQLite-specific features, so this is a connection-string and driver swap plus a real connection
pool — not a schema redesign.

**2. Local disk storage for audio files**
`audio_uploads/` is a folder on whatever single machine runs the Streamlit app, and `submissions.audio_path`
stores a path into it. At 5,000 uploads: unpredictable disk growth on one box, no redundancy if
that disk/machine dies, and slow playback for anyone not physically close to wherever it's hosted.
*Before launch:* move to object storage (S3 or equivalent); the database stores only the object
key/URL, never the file itself.

**3. Entity resolution degrading at volume — we already saw this happen in the 102-row test data**
The tiered matching rule (email → phone → name-as-validator-only) was built to fail safe: when
two rows share an email/phone but the name doesn't match, it doesn't guess — it creates a separate
record and flags the case (`source_records.match_confidence='flagged'`). In the real ingestion run
this fired exactly once (`Rohit Verma`/`R. Verma`, same email+phone, different name spelling) and
correctly stayed unmerged. But the *other* side of the same problem also showed up for real: 3
separate `Arjun Mehta` records and 2 each of `Deepak Nair`/`Karan Chopra`/`Vikram Mehta` exist in
the database right now, un-merged, because no email/phone bridges them — and a `Manish Bhatia`
that appears in source2 and source3 with no source1 anchor row is permanently split into two
people for the same reason. At 102 rows this is a handful of cases a human can eyeball. At 5,000
gig workers submitting through Task 3 with just a name and phone, the ratio of "genuinely different
people who happen to share a name" to "the same person typo'd their phone" only gets worse, and
nobody's manually eyeballing 5,000 rows.
*Before launch:* stop fully automating the ambiguous cases. Route anything that lands in
`source_records` as `flagged` (or that fails to match on email/phone at all despite a name
collision) into a human review queue instead of silently leaving it as an unmerged — or wrongly
merged — record either way.

**4. Streamlit's single-process, server-side session model**
Fine for a demo where one person uses the app at a time; not built to hold thousands of
concurrent users' session state in one process. It doesn't horizontally scale the way a stateless
API plus a separate frontend would.
*Before launch:* split into a proper backend API (handles the DB writes and audio-metric
extraction) with a lightweight frontend, or at minimum run multiple Streamlit instances behind a
load balancer with sticky sessions.

## Other things to change before launch

- **Upload validation client-side, before the upload even starts** — reject an obviously-wrong
  file size/duration/format in the browser, not after ffmpeg/pydub/librosa have already spent time
  processing something that was never going to work.
- **Retry-safe submissions** — an idempotency key per submission attempt, so a dropped connection
  mid-upload can't silently lose someone's audio or create a duplicate `submissions` row on retry.
- **Per-phone rate limiting** — separate from the identity-merge problem above: this is about
  catching accidental double-submits (someone tapping "Submit" twice on a slow connection), not
  about whether two *different* people share a phone.
- **Cost control on Task 2's LLM tagging** — 5,000 people means 5,000 OpenAI calls through the
  "Classify Skills" node. Individually cheap (short prompt, short response), but worth batching
  requests where the model supports it and setting a hard spend cap — unpredictable weekend
  traffic shouldn't turn into a surprise bill discovered on Monday.
- **Basic monitoring** — none of the above matters if failures fail silently. Alerting on
  submission failure rate and n8n execution failure rate would catch a problem while it's still a
  handful of people, not 5,000.
