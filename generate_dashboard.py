"""
generate_dashboard.py

Reads data/price_history.json and writes src/dashboard/data.js containing:
  window.PRICE_DATA  — records + per-platform chart series, keyed by session
  window.PRICE_META  — last_updated timestamp and total record count
"""
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/price_history.json")
DATA_JS_PATH = Path("src/dashboard/data.js")

_PLATFORM_ORDER = ["tickpick", "seatgeek", "ticketmaster"]


def _build_chart_series(records: list[dict]) -> dict[str, list[dict]]:
    """
    For each platform, produce [{x: checked_at ISO, y: min_price}] sorted by
    timestamp.  Only timestamps where price > 0 are included.
    """
    bucket: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        ts = r.get("checked_at", "")
        platform = r.get("platform", "unknown")
        price = float(r.get("price") or 0)
        if ts and price > 0:
            bucket[ts][platform].append(price)

    all_ts = sorted(bucket.keys())
    platforms = {p for ts_data in bucket.values() for p in ts_data}

    series: dict[str, list[dict]] = {}
    for platform in sorted(platforms, key=lambda p: _PLATFORM_ORDER.index(p) if p in _PLATFORM_ORDER else 99):
        points = [
            {"x": ts, "y": round(min(bucket[ts][platform]), 2)}
            for ts in all_ts
            if platform in bucket[ts]
        ]
        if points:
            series[platform] = points
    return series


def main() -> None:
    records: list[dict] = []
    if DB_PATH.exists():
        text = DB_PATH.read_text(encoding="utf-8").strip()
        if text:
            records = json.loads(text)

    by_key: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        key = f"{r.get('session_date', 'unknown')}|{r.get('session_type', 'unknown')}"
        by_key[key].append(r)

    grouped = {
        key: {
            "records": recs,
            "chart": _build_chart_series(recs),
        }
        for key, recs in by_key.items()
    }

    total = sum(len(v["records"]) for v in grouped.values())
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "total_records": total,
    }

    DATA_JS_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_JS_PATH.write_text(
        f"window.PRICE_DATA = {json.dumps(grouped, indent=2)};\n"
        f"window.PRICE_META = {json.dumps(meta)};\n",
        encoding="utf-8",
    )
    print(f"[generate_dashboard] {total} record(s) across {len(grouped)} session(s) → {DATA_JS_PATH}")


if __name__ == "__main__":
    main()
