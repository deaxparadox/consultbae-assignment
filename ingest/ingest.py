"""Task 1 — merge 3 source CSVs into consultbae.db (SQLite). See docs/specs/001 and ADR 0001."""
import json
import sqlite3
from pathlib import Path

import pandas as pd

from normalize import (
    looks_like_email,
    normalize_ctc,
    normalize_date,
    normalize_email,
    normalize_gig_rate,
    normalize_gig_status,
    normalize_name,
    normalize_phone,
    normalize_verified,
    parse_float,
    parse_int,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSIGNMENT_FILES = REPO_ROOT / "docs" / "assignment-files"
DB_PATH = REPO_ROOT / "consultbae.db"
LOG_PATH = REPO_ROOT / "ingest" / "ingestion_log.txt"

SCHEMA = """
CREATE TABLE people (
    person_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT,
    email TEXT,
    phone_normalized TEXT,
    phone_raw TEXT,
    city_raw TEXT,
    skill_tags TEXT,
    skills_raw TEXT,
    experience_years REAL,
    current_ctc_normalized INTEGER,
    current_ctc_raw TEXT,
    applied_date_normalized TEXT,
    applied_date_raw TEXT,
    gig_rate_normalized REAL,
    gig_rate_raw TEXT,
    gig_rate_unit TEXT,
    gig_status_normalized TEXT,
    gig_status_raw TEXT,
    verified INTEGER,
    projects_completed INTEGER
);

CREATE TABLE source_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    source_file TEXT NOT NULL,
    raw_row_json TEXT NOT NULL,
    match_tier TEXT NOT NULL,
    match_confidence TEXT NOT NULL
);

CREATE TABLE submissions (
    submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id INTEGER NOT NULL REFERENCES people(person_id),
    audio_path TEXT NOT NULL,
    duration_sec REAL,
    sample_rate_hz INTEGER,
    bitrate_kbps REAL,
    loudness_db REAL,
    created_at TEXT NOT NULL
);
"""


class Log:
    def __init__(self, path):
        self.lines = []
        self.path = path

    def __call__(self, msg):
        print(msg)
        self.lines.append(msg)

    def flush(self):
        self.path.write_text("\n".join(self.lines) + "\n")


class MergeEngine:
    """Tiered entity resolution: email -> phone -> name-as-validator-only. Per ADR 0001."""

    def __init__(self, conn, log):
        self.conn = conn
        self.log = log
        self.email_index = {}  # normalized email -> person_id
        self.phone_index = {}  # normalized phone -> person_id
        self.stats = {"rows_read": 0, "rows_skipped": 0, "people_created": 0,
                      "people_merged": 0, "flagged": 0}

    def _fetch_person(self, person_id):
        cur = self.conn.execute("SELECT * FROM people WHERE person_id = ?", (person_id,))
        cols = [d[0] for d in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row))

    def resolve(self, full_name, email_raw, phone_raw):
        """Returns (person_id, match_tier, match_confidence, is_new)."""
        norm_email = normalize_email(email_raw)
        norm_phone, phone_malformed = normalize_phone(phone_raw)
        if phone_malformed:
            self.log(f"  WARNING: phone '{phone_raw}' does not normalize to 10 digits — kept as raw-only, not used for matching")

        candidate_id, match_tier = None, "none"
        if norm_email and norm_email in self.email_index:
            candidate_id, match_tier = self.email_index[norm_email], "email"
        elif norm_phone and norm_phone in self.phone_index:
            candidate_id, match_tier = self.phone_index[norm_phone], "phone"

        if candidate_id is not None:
            existing = self._fetch_person(candidate_id)
            if normalize_name(existing["full_name"]) == normalize_name(full_name):
                self._merge_into(candidate_id, existing, norm_email, norm_phone)
                self.stats["people_merged"] += 1
                return candidate_id, match_tier, "high", False
            else:
                self.log(f"  FLAGGED: '{full_name}' matches existing person_id={candidate_id} "
                         f"('{existing['full_name']}') on {match_tier}, but names differ — "
                         f"NOT auto-merged, creating separate record")
                new_id = self._create_person(full_name, norm_email, norm_phone)
                self.stats["flagged"] += 1
                self.stats["people_created"] += 1
                return new_id, match_tier, "flagged", True

        new_id = self._create_person(full_name, norm_email, norm_phone)
        self.stats["people_created"] += 1
        return new_id, "none", "high", True

    def _create_person(self, full_name, norm_email, norm_phone):
        cur = self.conn.execute("INSERT INTO people (full_name) VALUES (?)", (full_name,))
        person_id = cur.lastrowid
        if norm_email:
            self.email_index.setdefault(norm_email, person_id)
        if norm_phone:
            self.phone_index.setdefault(norm_phone, person_id)
        return person_id

    def _merge_into(self, person_id, existing, norm_email, norm_phone):
        if norm_email and not existing.get("email"):
            self.conn.execute("UPDATE people SET email = ? WHERE person_id = ?", (norm_email, person_id))
        if norm_phone and not existing.get("phone_normalized"):
            self.conn.execute("UPDATE people SET phone_normalized = ? WHERE person_id = ?", (norm_phone, person_id))
        if norm_email:
            self.email_index.setdefault(norm_email, person_id)
        if norm_phone:
            self.phone_index.setdefault(norm_phone, person_id)

    def record_source(self, person_id, source_file, raw_row, match_tier, match_confidence):
        self.conn.execute(
            "INSERT INTO source_records (person_id, source_file, raw_row_json, match_tier, match_confidence) "
            "VALUES (?, ?, ?, ?, ?)",
            (person_id, source_file, json.dumps(raw_row, default=str), match_tier, match_confidence),
        )


def union_skills(existing_raw, new_skills):
    existing = set()
    if existing_raw:
        existing = {s.strip().lower() for s in existing_raw.split(",") if s.strip()}
    new = {s.strip().lower() for s in str(new_skills).split(",") if s.strip()} if new_skills else set()
    return ", ".join(sorted(existing | new)) if (existing | new) else None


def ingest_source1(conn, engine, log):
    """Full Name,Email,Phone,City,Experience (Years),Current CTC,Applied Date,Skills"""
    path = ASSIGNMENT_FILES / "source1_naukri_applicants.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    log(f"\n=== source1_naukri_applicants.csv: {len(df)} data rows in file ===")
    for _, row in df.iterrows():
        engine.stats["rows_read"] += 1
        raw_row = row.to_dict()
        person_id, tier, confidence, is_new = engine.resolve(row["Full Name"], row["Email"], row["Phone"])

        ctc_norm, ctc_raw = normalize_ctc(row["Current CTC"])
        date_norm, date_raw = normalize_date(row["Applied Date"])
        _, phone_malformed = normalize_phone(row["Phone"])
        norm_email = normalize_email(row["Email"])
        norm_phone, _ = normalize_phone(row["Phone"])

        existing = engine._fetch_person(person_id)
        conn.execute(
            """UPDATE people SET
                city_raw = COALESCE(city_raw, ?),
                phone_raw = COALESCE(phone_raw, ?),
                skills_raw = ?,
                experience_years = COALESCE(experience_years, ?),
                current_ctc_normalized = COALESCE(current_ctc_normalized, ?),
                current_ctc_raw = COALESCE(current_ctc_raw, ?),
                applied_date_normalized = COALESCE(applied_date_normalized, ?),
                applied_date_raw = COALESCE(applied_date_raw, ?),
                email = COALESCE(email, ?),
                phone_normalized = COALESCE(phone_normalized, ?)
               WHERE person_id = ?""",
            (row["City"], row["Phone"], union_skills(existing.get("skills_raw"), row["Skills"]),
             parse_float(row["Experience (Years)"]), ctc_norm, ctc_raw, date_norm, date_raw,
             norm_email, norm_phone, person_id),
        )
        engine.record_source(person_id, "source1_naukri_applicants.csv", raw_row, tier, confidence)


def ingest_source2(conn, engine, log):
    """email_id,worker_name,rate,location,status,skill_tags"""
    path = ASSIGNMENT_FILES / "source2_gig_workers.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    log(f"\n=== source2_gig_workers.csv: {len(df)} data rows in file ===")
    for idx, row in df.iterrows():
        raw_row = row.to_dict()
        line_no = idx + 2  # +1 header, +1 for 1-indexing

        if all(str(v).strip() == "" for v in raw_row.values()):
            log(f"  SKIPPED line {line_no}: fully blank row")
            engine.stats["rows_skipped"] += 1
            continue

        if not looks_like_email(row["email_id"]):
            log(f"  SKIPPED line {line_no}: malformed/shifted row (email_id column contains "
                f"'{row['email_id']}', not a valid email) — raw: {raw_row}")
            engine.stats["rows_skipped"] += 1
            continue

        engine.stats["rows_read"] += 1
        person_id, tier, confidence, _ = engine.resolve(row["worker_name"], row["email_id"], None)

        rate_norm, rate_unit, rate_raw = normalize_gig_rate(row["rate"])
        status_norm, status_raw = normalize_gig_status(row["status"])
        existing = engine._fetch_person(person_id)
        conn.execute(
            """UPDATE people SET
                city_raw = COALESCE(city_raw, ?),
                skills_raw = ?,
                gig_rate_normalized = COALESCE(gig_rate_normalized, ?),
                gig_rate_raw = COALESCE(gig_rate_raw, ?),
                gig_rate_unit = COALESCE(gig_rate_unit, ?),
                gig_status_normalized = COALESCE(gig_status_normalized, ?),
                gig_status_raw = COALESCE(gig_status_raw, ?)
               WHERE person_id = ?""",
            (row["location"], union_skills(existing.get("skills_raw"), row["skill_tags"]),
             rate_norm, rate_raw, rate_unit, status_norm, status_raw, person_id),
        )
        engine.record_source(person_id, "source2_gig_workers.csv", raw_row, tier, confidence)


def ingest_source3(conn, engine, log):
    """Name,Phone Number,City,Verified,Projects Completed"""
    path = ASSIGNMENT_FILES / "source3_cbnexus_contacts.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    log(f"\n=== source3_cbnexus_contacts.csv: {len(df)} data rows in file ===")
    header_values = {"Name", "Phone Number", "City", "Verified", "Projects Completed"}
    for idx, row in df.iterrows():
        raw_row = row.to_dict()
        line_no = idx + 2

        if set(str(v).strip() for v in raw_row.values()) == header_values:
            log(f"  SKIPPED line {line_no}: repeated header row embedded as data")
            engine.stats["rows_skipped"] += 1
            continue

        engine.stats["rows_read"] += 1
        person_id, tier, confidence, _ = engine.resolve(row["Name"], None, row["Phone Number"])

        conn.execute(
            """UPDATE people SET
                city_raw = COALESCE(city_raw, ?),
                phone_raw = COALESCE(phone_raw, ?),
                verified = COALESCE(verified, ?),
                projects_completed = COALESCE(projects_completed, ?)
               WHERE person_id = ?""",
            (row["City"], row["Phone Number"], normalize_verified(row["Verified"]),
             parse_int(row["Projects Completed"]), person_id),
        )
        engine.record_source(person_id, "source3_cbnexus_contacts.csv", raw_row, tier, confidence)


def main():
    log = Log(LOG_PATH)
    if DB_PATH.exists():
        DB_PATH.unlink()
        log(f"Removed existing {DB_PATH.name} — starting fresh")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript(SCHEMA)

    engine = MergeEngine(conn, log)
    ingest_source1(conn, engine, log)
    ingest_source2(conn, engine, log)
    ingest_source3(conn, engine, log)
    conn.commit()

    total_people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    total_source_records = conn.execute("SELECT COUNT(*) FROM source_records").fetchone()[0]

    log("\n=== SUMMARY ===")
    log(f"Rows read (excluding skipped): {engine.stats['rows_read']}")
    log(f"Rows skipped (malformed/blank): {engine.stats['rows_skipped']}")
    log(f"People created: {engine.stats['people_created']}")
    log(f"Rows merged into existing people: {engine.stats['people_merged']}")
    log(f"Flagged (name mismatch on email/phone match): {engine.stats['flagged']}")
    log(f"Total people in DB: {total_people}")
    log(f"Total source_records rows: {total_source_records}")

    conn.close()
    log.flush()
    print(f"\nLog written to {LOG_PATH}")


if __name__ == "__main__":
    main()
