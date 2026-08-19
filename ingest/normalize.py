"""Normalization helpers for Task 1 ingestion (ADR 0001)."""
import re
from datetime import datetime

PHONE_DIGITS_RE = re.compile(r"\D")

# Slash-separated dates are MM/DD/YYYY, hyphen-separated are DD-MM-YYYY
# (per ADR 0001, confirmed by out-of-range values proving the slot that must be the day).
_DATE_FORMATS = [
    ("%Y-%m-%d", None),          # ISO: 2026-08-08
    ("%m/%d/%Y", None),          # slash: 07/13/2026 -> MM/DD/YYYY
    ("%d-%m-%Y", None),          # hyphen: 24-07-2026 -> DD-MM-YYYY
    ("%d %b %Y", None),          # text month: 7 Jul 2026 / 15 Jul 2026
]


def normalize_phone(raw):
    """Return (normalized_10_digit_or_None, is_malformed_bool). Raw is kept separately by caller."""
    if raw is None:
        return None, False
    raw = str(raw).strip()
    if not raw:
        return None, False
    digits = PHONE_DIGITS_RE.sub("", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return None, True
    return digits, False


def normalize_email(raw):
    if raw is None:
        return None
    raw = str(raw).strip()
    if not raw:
        return None
    return raw.lower()


def looks_like_email(raw):
    if raw is None:
        return False
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(raw).strip()))


def normalize_name(raw):
    """Comparison key only (lowercase, whitespace-collapsed) — not for storage."""
    if raw is None:
        return None
    raw = re.sub(r"\s+", " ", str(raw).strip())
    return raw.lower()


def normalize_ctc(raw):
    """Returns (normalized_rupees_or_None, raw_str). <100 => lakhs, else already rupees."""
    if raw is None or str(raw).strip() == "":
        return None, raw
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, raw
    normalized = value * 100000 if value < 100 else value
    return int(round(normalized)), str(raw)


def normalize_date(raw):
    """Returns (iso_date_str_or_None, raw_str)."""
    if raw is None or str(raw).strip() == "":
        return None, raw
    text = str(raw).strip()
    for fmt, _ in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d"), text
        except ValueError:
            continue
    return None, text


def normalize_verified(raw):
    """Y/yes -> True, N/No -> False, blank/other -> None (explicitly unknown)."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("y", "yes"):
        return True
    if text in ("n", "no"):
        return False
    return None


_GIG_RATE_RE = re.compile(r"^([\d.]+)(k)?/(hr|month)$", re.IGNORECASE)


def normalize_gig_rate(raw):
    """Returns (numeric_value_or_None, unit_or_None, raw_str).

    Deliberately does NOT convert between hourly and monthly rates — that requires a
    working-hours assumption not present anywhere in the source data or design docs.
    Extracts the numeric amount and keeps its native unit instead of guessing. See
    DATA_ISSUES.md for the reasoning (found during implementation, not anticipated in ADR 0001).
    """
    if raw is None or str(raw).strip() == "":
        return None, None, raw
    text = str(raw).strip()
    match = _GIG_RATE_RE.match(text)
    if not match:
        return None, None, text
    amount, thousands, unit = match.groups()
    value = float(amount) * (1000 if thousands else 1)
    unit_normalized = "hourly" if unit.lower() == "hr" else "monthly"
    return value, unit_normalized, text


def normalize_gig_status(raw):
    if raw is None or str(raw).strip() == "":
        return None, raw
    return str(raw).strip().lower(), str(raw)


def parse_int(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def parse_float(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
