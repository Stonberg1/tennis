"""Entry point — runs all scrapers and triggers notifications."""
import asyncio
import src.config as config
from src.scrapers.tickpick import scrape_tickpick
from src.scrapers.seatgeek import scrape_seatgeek
from src.scrapers.ticketmaster_watcher import scrape_ticketmaster, check_presale
from src import database, notifier


async def run():
    all_records: list[dict] = []

    for date in config.TARGET_DATES:
        session = config.DATE_SESSION_MAP[date]
        ceiling = config.max_price_for(session)

        # Check for an active Ticketmaster presale before scraping listings
        try:
            presale_live = await check_presale(date)
            if presale_live:
                notifier.send_alert(
                    [{"platform": "ticketmaster", "session_date": date,
                      "session_type": session, "price": 0.0,
                      "section": "", "row": "", "quantity": 0,
                      "listing_url": ""}],
                    date=date,
                    session=session,
                    ceiling=ceiling,
                    subject_override=f"PRESALE LIVE — {session} session {date} on Ticketmaster",
                )
        except Exception as exc:
            print(f"[check_presale] error for {date}: {exc}")

        for scrape_fn in (scrape_tickpick, scrape_seatgeek, scrape_ticketmaster):
            try:
                records = await scrape_fn(date=date, session=session)
            except Exception as exc:
                print(f"[{scrape_fn.__name__}] error: {exc}")
                continue

            hits = [r for r in records if r.get("price", 9999) <= ceiling]
            all_records.extend(records)

            if hits:
                notifier.send_alert(hits, date=date, session=session, ceiling=ceiling)

    if all_records:
        database.append_records(all_records)


if __name__ == "__main__":
    asyncio.run(run())
