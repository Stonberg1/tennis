# Tennis Ticket Price Monitor

Automated monitor that scrapes TickPick, SeatGeek, and Ticketmaster every 15 minutes via GitHub Actions, stores price history, and sends Gmail alerts when tickets drop below your configured thresholds.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your credentials
python src/main.py
```

## Configuration

All settings are read from environment variables (or a `.env` file):

| Variable | Default | Description |
|---|---|---|
| `GMAIL_SENDER` | — | Gmail address used to send alerts |
| `GMAIL_APP_PASSWORD` | — | [Gmail App Password](https://support.google.com/accounts/answer/185833) |
| `GMAIL_RECEIVER` | — | Address that receives alerts |
| `MAX_PRICE_NIGHT` | `150` | Price ceiling for the night session (USD) |
| `MAX_PRICE_DAY` | `200` | Price ceiling for the day session (USD) |
| `TICKETMASTER_API_KEY` | — | [Ticketmaster Developer API key](https://developer.ticketmaster.com/) |
| `SEATGEEK_CLIENT_ID` | — | [SeatGeek API client_id](https://seatgeek.com/api) — register for a production key |

Target dates and session types are defined in `src/config.py`:

```python
TARGET_DATES  = ["2026-08-30", "2026-08-31"]
SESSION_TYPES = ["day", "night"]
```

## GitHub Actions

Add `GMAIL_SENDER`, `GMAIL_APP_PASSWORD`, and `GMAIL_RECEIVER` as [repository secrets](https://docs.github.com/en/actions/security-guides/encrypted-secrets). The workflow (`.github/workflows/monitor.yml`) runs every 15 minutes, commits updated price data, and regenerates the dashboard automatically.

## Dashboard

Open `src/dashboard/index.html` in a browser, or run `python generate_dashboard.py` to refresh `src/dashboard/data.js` from the latest price history.

## Project layout

```
.github/workflows/monitor.yml   GitHub Actions workflow
data/
  price_history.json            Append-only price log
  ticketmaster_state.json       Seen-event IDs (dedup)
src/
  config.py                     Environment-based configuration
  database.py                   JSON price history store
  main.py                       Orchestrator
  notifier.py                   Gmail alert sender
  scrapers/
    tickpick.py
    seatgeek.py
    ticketmaster_watcher.py
  dashboard/
    index.html                  Static dashboard
    data.js                     Generated — do not edit by hand
generate_dashboard.py           Rebuilds data.js from price history
requirements.txt
```
