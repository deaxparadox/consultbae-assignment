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

## Out of scope here
Bonus noise/quality estimate — attempt only if time remains after core Tasks 1-4 are solid; not
blocking for this spec's completion.
