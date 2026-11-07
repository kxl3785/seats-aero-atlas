"""Run every search in config.json and save the raw seats.aero results to data/raw/<name>.json.

Usage: python -m atlas.search [name ...]   (no names = run them all)
Each page of up to 1,000 results is one API call; Pro keys get 1,000 calls a day.
"""
import json
import socket
import sys
import time

from atlas.config import CFG, RAW, CABIN, SOURCES, airports, seats


def get_retry(path, params, tries=3):
    """seats.aero occasionally stalls; retry a timed-out request a couple of times."""
    for i in range(tries):
        try:
            return seats.get(path, params)
        except (socket.timeout, TimeoutError, OSError) as e:
            if i == tries - 1:
                raise
            print(f"  timeout, retrying ({e})", flush=True)
            time.sleep(5)


def fetch(origins, destinations, stop_above, max_pages):
    """Pages sorted by lowest mileage; stop once a whole page is priced above stop_above."""
    rows, cursor = [], None
    for _ in range(max_pages):
        page = get_retry("search", {
            "origin_airport": origins, "destination_airport": destinations,
            "start_date": CFG["start_date"], "end_date": CFG["end_date"], "cabins": CABIN,
            "sources": ",".join(SOURCES), "include_trips": "true", "order_by": "lowest_mileage",
            "take": 1000, "cursor": cursor, "skip": len(rows) or None})
        data = page.get("data", [])
        rows.extend(data)
        if not page.get("hasMore") or (stop_above and data and
                min(int(r.get("JMileageCost") or 0) for r in data) > stop_above):
            break
        cursor = page.get("cursor")
    return rows


def main(only):
    for s in CFG["searches"]:
        if only and s["name"] not in only:
            continue
        rows = fetch(airports(s["origins"]), airports(s["destinations"]), s.get("stop_above"), s.get("pages", 6))
        (RAW / f"{s['name']}.json").write_text(json.dumps(rows))
        latest = max((r["Date"] for r in rows), default=None)
        print(f"{s['name']}: {len(rows)} rows, latest {latest}, calls left {seats.quota_remaining}", flush=True)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
