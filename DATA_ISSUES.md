# Data Issues Report

Every row below traces to real output from `ingest/ingest.py`'s actual run against the 3 source
CSVs (see `ingest/ingestion_log.txt` for the raw log) and direct queries against the resulting
`consultbae.db`/`source_records` table — not written from memory or design notes. Run: 102 rows
processed across 3 files → 61 unique people, 41 cross/intra-file merges, 1 flagged case, 3 rows
skipped as malformed/blank.

| Issue | Where Found | Example | Resolution |
|---|---|---|---|
| No common ID field across the 3 sources | All 3 files | source1 has email+phone, source2 has email only, source3 has phone only | Tiered entity resolution: email → phone → name-as-validator-only. Phone is the only field common to source1 and source3; email is common to source1 and source2. |
| Fully blank row | source2, line 12 | Row is entirely empty fields | Detected and skipped, logged in `ingest/ingestion_log.txt` |
| Shifted/rotated columns (malformed row) | source2, line 20 | Row reads `"react, javascript, mysql", ISHA.CHOPRA95@..., Isha Chopra, 1406/hr, Pune, active` — values are offset one column to the left relative to the header | Detected via email-format validation on the `email_id` column (fails regex) and skipped. It's a corrupted duplicate of the already-correct row at line 7 (same person, same data), so no information was lost by skipping it. |
| Duplicate header row embedded as data | source3, line 16 | A data row whose values are literally `Name,Phone Number,City,Verified,Projects Completed` | Detected by comparing row values against the header set, skipped and logged. |
| Phone number format inconsistency (4 formats) | All 3 files | `+919000000254`, `9000000237`, `09000000287`, `+91-9000000131`, `919000000260` | Normalized to last-10-digits (strip `+91`/leading `0`/hyphens/spaces). Verified: every phone in all 3 files normalizes cleanly to 10 digits — no malformed phone numbers found in this dataset (checked programmatically against all 102 rows). |
| Email case inconsistency | source2 | `ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG`, `VARUN.SAXENA21@EXAMPLE.IN` (~14 of 30 valid source2 rows are all-caps) | Normalized via `.lower().strip()` before matching. |
| City casing/whitespace inconsistency | All 3 files | `pune` / `PUNE` / `Pune`; `Noida` / `NOIDA` / `Noida ` (trailing space); `gurugram ` / `Gurugram`; `Bangalore` / `bangalore` | **Judgment call: not normalized.** Stored verbatim as `city_raw`. Gurgaon/Gurugram is the same city under two names — canonicalizing city names crosses into geographic-alias territory beyond simple casing cleanup, and wasn't attempted. Flagged here instead of silently "fixed" so a reviewer can see the actual raw values. |
| Current CTC mixed units (lakhs vs. rupees) | source1 | `417964` (rupees) vs. `4.2` (lakhs) in the same column | `< 100` → treat as lakhs, ×100,000; `≥ 100` → already rupees. Both `current_ctc_normalized` and `current_ctc_raw` stored for auditability. |
| Gig rate mixed units (hourly vs. monthly) | source2 | `1415/hr` vs. `15k/month` in the same `rate` column | **Judgment call: not converted.** Converting between hourly and monthly rates requires a working-hours-per-month assumption that appears nowhere in the source data or the original design notes — silently picking one (e.g. 160 hrs/month) would misrepresent real rates. Instead, added a `gig_rate_unit` column (`hourly`/`monthly`) alongside the extracted numeric `gig_rate_normalized`, so the unit is preserved rather than guessed away. 16 hourly, 14 monthly in the actual data. |
| Date format inconsistency (4 formats) | source1 | `24-07-2026` (DD-MM), `2026-08-08` (ISO), `07/13/2026` (MM/DD — day 13 proves month can't be 13), `7 Jul 2026` (text month) | All normalized to ISO `YYYY-MM-DD` in `applied_date_normalized`; raw value kept in `applied_date_raw`. All 42 source1 dates parsed successfully — 0 parse failures. |
| `verified` field inconsistent encoding | source3 | `Y`, `yes`, `N`, `No`, case variants | Normalized: Y/yes → `true`, N/No → `false`. Distribution in real data: 14 true, 16 false, 31 unknown (people with no source3 row at all, correctly left `NULL` rather than defaulted to `false`). |
| Cross-file/intra-file name mismatch on a matched email or phone | source1, lines 25 & 31 | `R. Verma` and `Rohit Verma` share the exact same email (`rohit.verma13@mailtest.example.org`) and phone, but the name differs | Per the tiered-matching rule, a match on email/phone with a name mismatch is **flagged, not auto-merged** — the two rows became two separate `people` records (person_id 24 and 30), and the case is queryable via `source_records` (`match_confidence='flagged'`). This is the one flagged case in the real data; confirms the tier-3 name-validator guard is load-bearing, not just theoretical. |
| Same name, different people, no common field to merge on | source1 + source3 | 3 separate `Arjun Mehta` records (2 different phone numbers in source3, one of which also has no matching source1/source2 row); 2 separate `Deepak Nair`, `Karan Chopra`, `Vikram Mehta` records each | **Known limitation, not a bug.** Per the design rule, name-only matching is deliberately rejected (repeated common names in this data — 2× Priya, 2× Arjun, etc. — make it unsafe). Without a shared email or phone, these stay as separate records rather than risk a false merge. Safer failure mode than a wrong auto-merge, at the cost of some under-merging that a human reviewer would need to resolve manually at larger scale (see `TASK5_SCALING_NOTES.md`). |
| Person split across source2/source3 with no source1 anchor | source2 + source3 | `Manish Bhatia` — appears in source2 (email, no phone) and source3 (phone, no email), but never in source1 — so there's no field bridging the two rows | Correctly instantiated as **two separate `people` records** rather than guessed-merged on name alone. This is an inherent structural gap: source2 and source3 share no field directly, so any person present in both but absent from source1 cannot be automatically linked. |

## Implementation bug found and fixed (not a source-data issue, but disclosed for transparency)
While building the full systematic scan above, found that people created directly from source2 or
source3 (i.e. their first-seen row wasn't in source1) had their `email` or `phone_normalized`
column left `NULL` in storage — even though that same value was used in memory to match later
rows against them. Root cause: `_create_person()` in `ingest/ingest.py` only inserted `full_name`
on creation, leaving `email`/`phone_normalized` to be filled in by each source-specific `UPDATE`
statement afterward — and two of the three per-source `UPDATE`s were missing those columns. Fixed
by writing `email`/`phone_normalized` directly at row-creation time; re-ran the full ingestion and
re-verified the scan found zero remaining cases of this pattern.

## Checks performed
- **Malformed/blank rows**: full pass across all 102 processed rows plus the 3 skipped ones — see
  above and `ingest/ingestion_log.txt`.
- **Phone/email format validity**: every phone (102 rows) programmatically checked to confirm it
  normalizes to exactly 10 digits; every email checked against a standard email regex. Zero
  failures found in either check.
- **Range sanity**: `experience_years` (0–40), `current_ctc_normalized` (₹50,000–₹1,00,00,000),
  `projects_completed` (0–100) — zero out-of-range values found.
- **Duplicate detection**: checked for duplicate `phone_normalized` and duplicate `email` values
  across the `people` table — found exactly one pair (the flagged Rohit Verma / R. Verma case
  above; both fields collide because it's the same underlying data, correctly not double-merged).
- **Date parse failures**: checked for any `applied_date_raw` that failed to normalize — zero
  failures across all 42 source1 rows.
