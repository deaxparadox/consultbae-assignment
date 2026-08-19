# Spec 003: Task 3 — Mini Audio Collection App

**Branch:** `main` (base: `main`).

## What's being built
A Streamlit app with two views: (1) a submission form — name, phone, record audio
(`st.audio_input()`) or upload a file — that writes a `people` row (if the person is new, matched by
the same phone-normalization rule as Task 1) and a `submissions` row with extracted audio properties;
(2) a listing view — all submissions with a play button and their properties table.

## Design rationale
- Audio metric ownership is split to avoid library disagreement on the same value (verified via web
  research during the design pass): `pydub` owns duration/sample rate/bitrate (WAV bitrate computed
  explicitly as `sample_rate × bit_depth × channels`, not trusted from metadata); `librosa` owns
  loudness only, via frame-based RMS → dB (`librosa.feature.rms` → `amplitude_to_db`), not pydub's
  whole-file dBFS. No metric is computed by both.
- `st.audio_input()` chosen over a third-party recorder component — built into Streamlit core, no
  extra dependency/version risk. Known minor risk: occasional slow/hung save after stopping a
  recording — test early; `audio-recorder-streamlit` is the fallback if it proves flaky.
- New submitters via this app have no skills data — this is exactly why Task 2's read query is
  guarded (ADR 0001) to not send them to the LLM tagging step.
- Runs on host directly (not containerized), using SQLite path `./consultbae.db` — must exist with
  the Task 1 schema before this app is demoed (schema-only is enough, doesn't need populated data).

## Implementation
- `audio_app/` directory: `app.py`, `requirements.txt` additions (`streamlit`, `pydub`, `librosa`).
- ffmpeg required as a system dependency for pydub — already confirmed installed.
- Person lookup on submit: normalize the entered phone the same way as Task 1, match against
  existing `people`, create a new row only if no match.
- Store audio files under `audio_uploads/` (gitignored — not committed, regenerable/demo data).
- Deployment: run locally for the demo recording (assignment explicitly allows this). Cloud
  deployment (Streamlit Cloud/Render) is optional stretch only, not required.

## Amendment (found during implementation)
- Python 3.13 (the installed interpreter) removed the stdlib `audioop` module (PEP 594), which
  `pydub` imports unconditionally. Fix was the official `audioop-lts` PyPI backport (added to
  `requirements.txt` as `audioop-lts; python_version >= "3.13"`), not a Python downgrade or a
  pydub replacement — root cause is a stdlib removal with a known, maintained backport, not a
  design problem.
- Bitrate is computed as the decoded PCM bitrate (`sample_rate × bit_depth × channels`) uniformly
  for all formats, not just WAV — pydub doesn't expose the original container's encoded bitrate
  (e.g. an mp3/webm's actual compressed bitrate) without extra tooling (ffprobe parsing), so this
  is a deliberate simplification: consistent and defensible across formats, at the cost of not
  reflecting a compressed file's true on-disk bitrate. Worth being able to explain this trade-off
  live if asked.
- End-to-end verified via browser automation against the running app: submitted a synthetic test
  WAV through the upload path, confirmed the 4 extracted metrics matched a local direct-function-call
  sanity check exactly, and confirmed the listing view shows the same values with working audio
  playback. Test person/submission/audio file were then deleted so the DB stays in the clean
  Task 1 + Task 2 state (61 people, 0 submissions) for the real demo recording.

## Out of scope here
Bonus noise/quality estimate — attempt only if time remains after core Tasks 1-4 are solid; not
blocking for this spec's completion.
