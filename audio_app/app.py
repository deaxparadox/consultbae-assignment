"""Task 3 — Mini audio collection app. See docs/specs/003 and ADR 0001."""
import sys
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "ingest"))
from normalize import normalize_phone  # noqa: E402

from audio_metrics import extract_all_metrics  # noqa: E402

DB_PATH = REPO_ROOT / "consultbae.db"
AUDIO_DIR = REPO_ROOT / "audio_uploads"
AUDIO_DIR.mkdir(exist_ok=True)


def get_conn():
    if not DB_PATH.exists():
        st.error(
            f"Database not found at {DB_PATH}. Run Task 1's ingestion script "
            f"(`ingest/ingest.py`) first — it creates the schema this app writes into."
        )
        st.stop()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def find_or_create_person(conn, full_name, phone_raw):
    norm_phone, malformed = normalize_phone(phone_raw)
    if malformed or norm_phone is None:
        st.warning(
            f"Phone number '{phone_raw}' doesn't normalize to a valid 10-digit number — "
            f"a new person record will still be created, but it won't be matchable against "
            f"other sources by phone."
        )

    if norm_phone:
        row = conn.execute(
            "SELECT person_id FROM people WHERE phone_normalized = ?", (norm_phone,)
        ).fetchone()
        if row:
            return row[0]

    cur = conn.execute(
        "INSERT INTO people (full_name, phone_normalized, phone_raw) VALUES (?, ?, ?)",
        (full_name, norm_phone, phone_raw),
    )
    conn.commit()
    return cur.lastrowid


def save_audio_file(uploaded_audio):
    suffix = Path(getattr(uploaded_audio, "name", "recording.wav")).suffix or ".wav"
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = AUDIO_DIR / filename
    dest.write_bytes(uploaded_audio.getvalue())
    return dest


def submit_view():
    st.header("Submit a recording")
    full_name = st.text_input("Full name")
    phone = st.text_input("Phone number")

    st.write("Record audio, or upload a file instead:")
    recorded = st.audio_input("Record")
    uploaded = st.file_uploader("Or upload an audio file", type=["wav", "mp3", "ogg", "webm", "m4a"])
    audio_source = recorded or uploaded

    if st.button("Submit", type="primary"):
        if not full_name.strip() or not phone.strip():
            st.error("Name and phone number are both required.")
            return
        if audio_source is None:
            st.error("Record audio or upload a file before submitting.")
            return

        with st.spinner("Extracting audio properties..."):
            audio_path = save_audio_file(audio_source)
            metrics = extract_all_metrics(audio_path)

        conn = get_conn()
        person_id = find_or_create_person(conn, full_name.strip(), phone.strip())
        conn.execute(
            """INSERT INTO submissions
               (person_id, audio_path, duration_sec, sample_rate_hz, bitrate_kbps, loudness_db, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                person_id,
                str(audio_path.relative_to(REPO_ROOT)),
                metrics["duration_sec"],
                metrics["sample_rate_hz"],
                metrics["bitrate_kbps"],
                metrics["loudness_db"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

        st.success("Submission recorded.")
        st.json(metrics)


def submissions_view():
    st.header("All submissions")
    conn = get_conn()
    rows = conn.execute(
        """SELECT s.submission_id, p.full_name, p.phone_raw, s.audio_path, s.duration_sec,
                  s.sample_rate_hz, s.bitrate_kbps, s.loudness_db, s.created_at
           FROM submissions s JOIN people p ON s.person_id = p.person_id
           ORDER BY s.created_at DESC"""
    ).fetchall()
    conn.close()

    if not rows:
        st.info("No submissions yet.")
        return

    for row in rows:
        (sub_id, name, phone, audio_path, duration, sample_rate, bitrate, loudness, created_at) = row
        with st.container(border=True):
            st.write(f"**{name}** ({phone}) — submitted {created_at}")
            full_path = REPO_ROOT / audio_path
            if full_path.exists():
                st.audio(str(full_path))
            else:
                st.warning(f"Audio file missing on disk: {audio_path}")
            st.table(
                {
                    "duration_sec": [duration],
                    "sample_rate_hz": [sample_rate],
                    "bitrate_kbps": [bitrate],
                    "loudness_db": [loudness],
                }
            )


def main():
    st.set_page_config(page_title="ConsultBae Audio Collection", layout="centered")
    st.title("ConsultBae — Mini Audio Collection App")
    page = st.sidebar.radio("View", ["Submit", "All Submissions"])
    if page == "Submit":
        submit_view()
    else:
        submissions_view()


if __name__ == "__main__":
    main()
