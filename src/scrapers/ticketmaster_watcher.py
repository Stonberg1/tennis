"""
Ticketmaster availability watcher.

Uses a simple state file (data/ticketmaster_state.json) to track which
listings have already been seen so only new ones trigger alerts.

Two public functions:
  scrape_ticketmaster() — returns new listing records (deduped via state file)
  check_presale()       — returns True if a presale is currently live
"""
import json
from datetime import datetime, timezone
import httpx
from pathlib import Path
import src.config as config

_STATE_PATH = Path(__file__).parent.parent.parent / "data" / "ticketmaster_state.json"
_DISCOVERY_URL = "https://app.ticketmaster.com/discovery/v2/events.json"
# Keywords used to identify US Open tennis events in Discovery API results
_US_OPEN_KEYWORDS = ("us open", "usta", "flushing", "arthur ashe")


def _load_state() -> dict:
    if _STATE_PATH.exists():
        return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _base_params(date: str) -> dict:
    """Build the common Discovery API query params for *date*."""
    return {
        "apikey": config.TICKETMASTER_API_KEY,
        "keyword": "US Open Tennis",
        "startDateTime": f"{date}T00:00:00Z",
        "endDateTime": f"{date}T23:59:59Z",
        "size": 100,
    }


def _is_presale_active(event: dict) -> bool:
    """
    Return True if any presale window in ``event.sales.presales`` is currently live.
    Presale objects expose ``startDateTime`` and ``endDateTime`` in ISO-8601 UTC.
    """
    now = datetime.now(timezone.utc)
    for presale in event.get("sales", {}).get("presales", []):
        try:
            start = datetime.fromisoformat(
                presale["startDateTime"].replace("Z", "+00:00")
            )
            end = datetime.fromisoformat(
                presale["endDateTime"].replace("Z", "+00:00")
            )
            if start <= now <= end:
                return True
        except (KeyError, ValueError):
            continue
    return False


async def scrape_ticketmaster(*, date: str, session: str) -> list[dict]:
    """
    Fetch Ticketmaster listings for US Open on *date* and return only newly-seen ones.
    Already-seen event IDs are persisted in data/ticketmaster_state.json.
    """
    if not config.TICKETMASTER_API_KEY:
        print("[ticketmaster] TICKETMASTER_API_KEY not set — skipping.")
        return []

    records: list[dict] = []
    state = _load_state()
    seen: set[str] = set(state.get(date, []))

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(_DISCOVERY_URL, params=_base_params(date))
            resp.raise_for_status()
        except Exception as exc:
            print(f"[ticketmaster] request failed for {date}: {exc}")
            return records

    data = resp.json()
    events = data.get("_embedded", {}).get("events", []) if "_embedded" in data else []

    new_seen: list[str] = list(seen)
    for event in events:
        event_id: str = event.get("id", "")
        if event_id in seen:
            continue

        name = (event.get("name") or "").lower()
        if not any(kw in name for kw in _US_OPEN_KEYWORDS):
            continue

        price_ranges = event.get("priceRanges", [])
        price = float(price_ranges[0].get("min", 0)) if price_ranges else 0.0
        # Prefer the canonical URL from the API over a constructed fallback
        listing_url = event.get("url") or (
            f"https://www.ticketmaster.com/event/{event_id}" if event_id else ""
        )
        records.append({
            "platform": "ticketmaster",
            "session_date": date,
            "session_type": session,
            "price": price,
            "section": "",
            "row": "",
            "quantity": 1,
            "listing_url": listing_url,
        })
        new_seen.append(event_id)

    state[date] = new_seen
    _save_state(state)
    print(f"[ticketmaster] {date}: {len(records)} new listing(s) returned")
    return records


async def check_presale(date: str) -> bool:
    """
    Return True if a presale for the US Open on *date* is currently live on
    Ticketmaster.  Presale windows are read from ``sales.presales`` in each
    matching Discovery API event.  Fires a console note when one is found.
    """
    if not config.TICKETMASTER_API_KEY:
        print("[ticketmaster] TICKETMASTER_API_KEY not set — cannot check presale.")
        return False

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(_DISCOVERY_URL, params=_base_params(date))
            resp.raise_for_status()
        except Exception as exc:
            print(f"[ticketmaster] presale check failed for {date}: {exc}")
            return False

    data = resp.json()
    events = data.get("_embedded", {}).get("events", []) if "_embedded" in data else []

    for event in events:
        name = (event.get("name") or "").lower()
        if not any(kw in name for kw in _US_OPEN_KEYWORDS):
            continue
        if _is_presale_active(event):
            print(
                f"[ticketmaster] PRESALE ACTIVE — {event.get('name')} on {date}"
            )
            return True

    print(f"[ticketmaster] no active presale found for {date}")
    return False
