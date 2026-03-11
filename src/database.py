"""
JSON-backed price history store.

Schema for each record:
{
    "checked_at": "<ISO-8601 UTC timestamp>",
    "platform": "<scraper name>",
    "session_date": "<YYYY-MM-DD>",
    "session_type": "<day|night>",
    "price": <float>,
    "section": "<str>",
    "row": "<str>",
    "quantity": <int>,
    "listing_url": "<str>"
}
"""
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent / "data" / "price_history.json"


def load_all() -> list[dict]:
    """Return every record stored in the price history file."""
    if not _DB_PATH.exists():
        return []
    text = _DB_PATH.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def _save(records: list[dict]) -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DB_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")


def append_records(records: list[dict]) -> None:
    """Append new price records, stamping each with the current UTC time."""
    if not records:
        return
    existing = load_all()
    now = datetime.now(timezone.utc).isoformat()
    for record in records:
        record.setdefault("checked_at", now)
    existing.extend(records)
    _save(existing)


def get_recent_records(hours: int = 4) -> list[dict]:
    """Return records whose timestamp is within the last *hours* hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = []
    for record in load_all():
        try:
            ts = datetime.fromisoformat(record["checked_at"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff:
                result.append(record)
        except (KeyError, ValueError):
            continue
    return result
