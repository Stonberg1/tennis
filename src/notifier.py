"""
Email notifications via Gmail SMTP SSL (port 465).

One consolidated multipart/alternative email is sent per call — plain text
for clients that don't render HTML, plus an HTML version with a price table.

Deduplication: any listing_url that already appears in the price history
within the past 4 hours is considered already-alerted and is suppressed so
the same listing doesn't re-trigger an email on every 15-minute run.
"""
import smtplib
import textwrap
from datetime import datetime, timezone
from email.message import EmailMessage

import src.config as config
import src.database as database


# ── Deduplication ─────────────────────────────────────────────────────────────

def _recently_alerted_urls() -> set[str]:
    """Return listing_urls seen (and therefore alerted) in the past 4 hours."""
    return {
        r["listing_url"]
        for r in database.get_recent_records(hours=4)
        if r.get("listing_url")
    }


def _deduplicate(hits: list[dict]) -> list[dict]:
    """Filter out any listing whose URL was already alerted in the past 4 hours."""
    alerted = _recently_alerted_urls()
    fresh, skipped = [], 0
    for h in hits:
        url = h.get("listing_url", "")
        if url and url in alerted:
            skipped += 1
        else:
            fresh.append(h)
    if skipped:
        print(f"[notifier] {skipped} duplicate listing(s) suppressed (seen within 4 h).")
    return fresh


# ── HTML / plain-text builders ────────────────────────────────────────────────

_TBL = "border-collapse:collapse;width:100%;font-family:system-ui,sans-serif;font-size:14px;"
_TH  = "background:#1a1a2e;color:#fff;padding:8px 12px;text-align:left;border:1px solid #ccc;"
_TD  = "padding:8px 12px;border:1px solid #ddd;vertical-align:top;"
_TDA = "padding:8px 12px;border:1px solid #ddd;vertical-align:top;background:#f4f7ff;"


def _build_html(hits: list[dict], *, date: str, session: str, ceiling: int) -> str:
    rows_html = []
    for i, h in enumerate(hits):
        td = _TDA if i % 2 else _TD
        section  = h.get("section") or "—"
        row_val  = h.get("row")     or "—"
        url      = h.get("listing_url", "")
        buy_cell = (
            f'<a href="{url}" style="color:#1a6ef5;font-weight:bold;">Buy</a>'
            if url else "—"
        )
        rows_html.append(f"""\
        <tr>
          <td style="{td}">{h.get('session_date', date)}</td>
          <td style="{td}">{h.get('session_type', session)}</td>
          <td style="{td}">{h.get('platform', '')}</td>
          <td style="{td}">{section} / {row_val}</td>
          <td style="{td}"><strong>${h.get('price', 0):.0f}</strong></td>
          <td style="{td}">{h.get('quantity', 1)}</td>
          <td style="{td}">{buy_cell}</td>
        </tr>""")

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return textwrap.dedent(f"""\
        <!DOCTYPE html>
        <html lang="en">
        <body style="font-family:system-ui,sans-serif;max-width:820px;margin:0 auto;padding:16px;">
          <h2 style="color:#1a1a2e;margin-bottom:4px;">
            &#127934; Tennis ticket alert &#8212; {session} session on {date} under ${ceiling}
          </h2>
          <p style="color:#555;margin-top:4px;">
            <strong>{len(hits)}</strong> listing(s) at or below
            <strong>${ceiling}</strong>, sorted by price.
          </p>
          <table style="{_TBL}">
            <thead>
              <tr>
                <th style="{_TH}">Date</th>
                <th style="{_TH}">Session</th>
                <th style="{_TH}">Platform</th>
                <th style="{_TH}">Section / Row</th>
                <th style="{_TH}">Price</th>
                <th style="{_TH}">Qty</th>
                <th style="{_TH}">Buy</th>
              </tr>
            </thead>
            <tbody>
        {''.join(rows_html)}
            </tbody>
          </table>
          <p style="color:#bbb;font-size:11px;margin-top:12px;">Generated {generated}</p>
        </body>
        </html>""")


def _build_plain(hits: list[dict], *, date: str, session: str, ceiling: int) -> str:
    header = (
        f"Tennis ticket alert: {session} session on {date} under ${ceiling}\n"
        f"Found {len(hits)} listing(s) at or below ${ceiling} (sorted by price):\n\n"
        f"{'Date':<12} {'Session':<8} {'Platform':<14} {'Sec/Row':<20} {'Price':>6}  {'Qty':>4}  URL\n"
        + "-" * 92
    )
    lines = [header]
    for h in hits:
        sec_row = f"{h.get('section','') or '—'}/{h.get('row','') or '—'}"
        lines.append(
            f"{h.get('session_date', date):<12} "
            f"{h.get('session_type', session):<8} "
            f"{h.get('platform', ''):<14} "
            f"{sec_row:<20} "
            f"${h.get('price', 0):>5.0f}  "
            f"{h.get('quantity', 1):>4}  "
            f"{h.get('listing_url', '')}"
        )
    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────────────────

def send_alert(
    hits: list[dict],
    *,
    date: str,
    session: str,
    ceiling: int,
    subject_override: str = "",
) -> None:
    """
    Send one consolidated HTML+plain email for all *hits* that haven't been
    alerted in the past 4 hours.  No-ops gracefully if credentials are absent
    or every listing is a duplicate.
    """
    if not config.GMAIL_SENDER or not config.GMAIL_APP_PASSWORD:
        print("[notifier] Gmail credentials not configured — skipping email.")
        return

    new_hits = _deduplicate(hits)
    if not new_hits:
        print("[notifier] All listings already alerted within 4 h — nothing to send.")
        return

    # Sort by price ascending for both the table and the subject line
    new_hits.sort(key=lambda r: r.get("price", 0))

    n = len(new_hits)
    subject = subject_override or (
        f"\U0001f3be Tennis tickets under ${ceiling}: "
        f"{session} session {date} "
        f"({n} listing{'s' if n != 1 else ''})"
    )

    html  = _build_html(new_hits,  date=date, session=session, ceiling=ceiling)
    plain = _build_plain(new_hits, date=date, session=session, ceiling=ceiling)

    msg = EmailMessage()
    msg["From"]    = config.GMAIL_SENDER
    msg["To"]      = config.GMAIL_RECEIVER
    msg["Subject"] = subject
    msg.set_content(plain)                      # plain-text part
    msg.add_alternative(html, subtype="html")   # HTML part

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(config.GMAIL_SENDER, config.GMAIL_APP_PASSWORD)
        smtp.send_message(msg)

    print(f"[notifier] Alert sent: {n} listing(s) → {config.GMAIL_RECEIVER}.")


# ── Test harness ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    _MOCK_HITS = [
        {
            "platform": "tickpick",
            "session_date": "2026-08-30",
            "session_type": "day",
            "price": 142.00,
            "section": "Upper 301",
            "row": "C",
            "quantity": 2,
            "listing_url": "https://www.tickpick.com/tickets/us-open-tennis/?listing=123",
        },
        {
            "platform": "seatgeek",
            "session_date": "2026-08-31",
            "session_type": "night",
            "price": 119.00,
            "section": "Loge 119",
            "row": "F",
            "quantity": 4,
            "listing_url": "https://seatgeek.com/e/us-open-tennis?listing_id=456",
        },
    ]

    print("[test] Sending test alert email…")
    # Bypass dedup: mock URLs won't be in an empty or fresh price_history.json
    send_alert(
        _MOCK_HITS,
        date="2026-08-30 / 2026-08-31",
        session="day + night",
        ceiling=150,
        subject_override="[TEST] Tennis monitor — verify Gmail credentials",
    )
    print("[test] Done. Check your inbox at", config.GMAIL_RECEIVER)
    sys.exit(0)
