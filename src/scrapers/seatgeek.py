"""
SeatGeek scraper — uses the SeatGeek API v2.

Requires a client_id from https://seatgeek.com/api (free registration).
Set the SEATGEEK_CLIENT_ID environment variable / GitHub Secret with your
production key.  Without it requests are anonymous and may be rate-limited
or return no results.
"""
import httpx
import src.config as config

_BASE = "https://api.seatgeek.com/2"
_SG_BASE_URL = "https://seatgeek.com"
# Keywords used to identify US Open tennis events in search results
_US_OPEN_KEYWORDS = ("us open", "usta", "flushing")


def _build_params(extra: dict) -> dict:
    """Merge common auth parameters with *extra*."""
    params = dict(extra)
    if config.SEATGEEK_CLIENT_ID:
        params["client_id"] = config.SEATGEEK_CLIENT_ID
    return params


async def _find_sg_events(
    client: httpx.AsyncClient, target_date: str
) -> list[dict]:
    """Return SeatGeek event objects for US Open tennis on *target_date*."""
    params = _build_params({
        "q": "US Open Tennis",
        "datetime_local.gte": f"{target_date}T00:00:00",
        "datetime_local.lte": f"{target_date}T23:59:59",
        "per_page": 10,
    })
    resp = await client.get(f"{_BASE}/events", params=params)
    resp.raise_for_status()
    events = resp.json().get("events", [])
    return [
        e for e in events
        if any(kw in (e.get("title") or "").lower() for kw in _US_OPEN_KEYWORDS)
    ]


async def scrape_seatgeek(*, date: str, session: str) -> list[dict]:
    """
    Find US Open events on *date* via SeatGeek, then fetch all their listings.
    Listing URLs point to the specific SeatGeek listing page.
    """
    records: list[dict] = []

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            events = await _find_sg_events(client, date)
        except Exception as exc:
            print(f"[seatgeek] event search failed for {date}: {exc}")
            return records

        if not events:
            print(f"[seatgeek] no US Open events found for {date}")
            return records

        for event in events:
            event_id = event.get("id")
            # SeatGeek event objects include a direct URL to the event page
            event_url: str = event.get("url") or f"{_SG_BASE_URL}/e/{event_id}"

            try:
                resp = await client.get(
                    f"{_BASE}/listings",
                    params=_build_params({"event_id": event_id, "per_page": 200}),
                )
                resp.raise_for_status()
            except Exception as exc:
                print(f"[seatgeek] listing fetch failed (event {event_id}): {exc}")
                continue

            for listing in resp.json().get("listings", []):
                try:
                    price = float(listing.get("price") or 0)
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue

                listing_id = listing.get("id") or listing.get("listing_id") or ""
                # Build direct listing URL: event page with listing anchor
                listing_url = (
                    f"{event_url}?listing_id={listing_id}"
                    if listing_id
                    else event_url
                )
                records.append({
                    "platform": "seatgeek",
                    "session_date": date,
                    "session_type": session,
                    "price": price,
                    "section": str(listing.get("section") or ""),
                    "row": str(listing.get("row") or ""),
                    "quantity": int(listing.get("quantity") or 1),
                    "listing_url": listing_url,
                })

    print(f"[seatgeek] {date}: {len(records)} listing(s) returned")
    return records
