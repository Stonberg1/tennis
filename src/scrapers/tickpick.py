"""
TickPick scraper.

WARNING — REVERSE-ENGINEERED ENDPOINTS
  TickPick does not publish a public API.  The endpoints below
  (  /api/events  and  /api/listing  ) were inferred by inspecting
  network traffic on tickpick.com and are NOT officially documented.
  They may change or be removed without notice.  If requests start
  returning 4xx/5xx or unexpected JSON shapes, check the TickPick
  website in a browser with DevTools open and update the URLs and
  response-parsing logic accordingly.
"""
import httpx

_BASE = "https://www.tickpick.com"
_SEARCH_URL = f"{_BASE}/api/events"
_LISTINGS_URL = f"{_BASE}/api/listing"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; tennis-monitor/1.0)",
    "Accept": "application/json",
    "Referer": _BASE + "/",
}
# Keywords used to identify US Open tennis events in search results
_US_OPEN_KEYWORDS = ("us open", "usta", "flushing", "arthur ashe")


async def _find_event_ids(
    client: httpx.AsyncClient, target_date: str
) -> list[tuple[str, str]]:
    """
    Search TickPick for US Open tennis events on *target_date*.
    Returns a list of (event_id, event_url) tuples.
    """
    params = {
        "q": "US Open Tennis",
        "startDate": target_date,
        "endDate": target_date,
    }
    resp = await client.get(_SEARCH_URL, params=params, headers=_HEADERS)
    resp.raise_for_status()

    try:
        body = resp.json()
    except Exception as exc:
        raise ValueError(
            f"[tickpick] event search returned non-JSON (status {resp.status_code}): {exc}"
        ) from exc

    # TickPick returns either a bare list or a dict with an "events" / "data" key
    raw = body if isinstance(body, list) else body.get("events", body.get("data", []))

    results: list[tuple[str, str]] = []
    for event in raw:
        name: str = (event.get("name") or event.get("title") or "").lower()
        if any(kw in name for kw in _US_OPEN_KEYWORDS):
            eid = str(event.get("id") or event.get("eventId") or "")
            slug = event.get("slug") or event.get("urlSlug") or eid
            if eid:
                event_url = f"{_BASE}/tickets/{slug}/" if slug else ""
                results.append((eid, event_url))
    return results


async def scrape_tickpick(*, date: str, session: str) -> list[dict]:
    """Find US Open events on *date* via the TickPick API and return all listings."""
    records: list[dict] = []

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            event_ids = await _find_event_ids(client, date)
        except Exception as exc:
            print(f"[tickpick] event search failed for {date}: {exc}")
            return records

        if not event_ids:
            print(f"[tickpick] no US Open events found for {date}")
            return records

        for event_id, event_url in event_ids:
            try:
                resp = await client.get(
                    _LISTINGS_URL,
                    params={"eventId": event_id},
                    headers=_HEADERS,
                )
                resp.raise_for_status()
            except Exception as exc:
                print(f"[tickpick] listing fetch failed (event {event_id}): {exc}")
                continue

            try:
                body = resp.json()
            except Exception as exc:
                print(
                    f"[tickpick] listing response for event {event_id} was not valid JSON "
                    f"(status {resp.status_code}) — the reverse-engineered endpoint may "
                    f"have changed: {exc}"
                )
                continue

            listings = (
                body if isinstance(body, list)
                else body.get("listings", body.get("data", []))
            )

            for listing in listings:
                try:
                    price = float(
                        listing.get("price") or listing.get("listPrice") or 0
                    )
                except (TypeError, ValueError):
                    continue
                if price <= 0:
                    continue

                listing_id = listing.get("listingId") or listing.get("id") or ""
                listing_url = (
                    f"{event_url}?listing={listing_id}"
                    if listing_id and event_url
                    else event_url
                )
                records.append({
                    "platform": "tickpick",
                    "session_date": date,
                    "session_type": session,
                    "price": price,
                    "section": str(listing.get("section") or ""),
                    "row": str(listing.get("row") or ""),
                    "quantity": int(listing.get("quantity") or 1),
                    "listing_url": listing_url,
                })

    print(f"[tickpick] {date}: {len(records)} listing(s) returned")
    return records
