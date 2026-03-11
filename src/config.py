"""
Central configuration — all settings are read from environment variables.
Copy .env.example to .env and fill in your values for local development.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Email ---
GMAIL_SENDER: str = os.environ.get("GMAIL_SENDER", "")
GMAIL_APP_PASSWORD: str = os.environ.get("GMAIL_APP_PASSWORD", "")
GMAIL_RECEIVER: str = os.environ.get("GMAIL_RECEIVER", "")

# --- Ticketmaster ---
TICKETMASTER_API_KEY: str = os.environ.get("TICKETMASTER_API_KEY", "")

# --- SeatGeek ---
SEATGEEK_CLIENT_ID: str = os.environ.get("SEATGEEK_CLIENT_ID", "")

# --- Price thresholds (USD) ---
MAX_PRICE_NIGHT: int = int(os.environ.get("MAX_PRICE_NIGHT", 150))
MAX_PRICE_DAY: int = int(os.environ.get("MAX_PRICE_DAY", 200))

# --- Event schedule ---
TARGET_DATES: list[str] = ["2026-08-30", "2026-08-31"]
SESSION_TYPES: list[str] = ["day", "night"]

# Convenience mapping: date → session type
DATE_SESSION_MAP: dict[str, str] = dict(zip(TARGET_DATES, SESSION_TYPES))

def max_price_for(session: str) -> int:
    """Return the price ceiling for a given session type."""
    return MAX_PRICE_NIGHT if session == "night" else MAX_PRICE_DAY
