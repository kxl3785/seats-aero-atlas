#!/usr/bin/env python3
"""Search seats.aero cached award availability (Partner API, Pro tier).

API key is read from SEATS_AERO_API_KEY, or from a .env file next to this script
(either SEATS_AERO_API_KEY=... or just the bare key).

Examples:
  ./seats.py search SFO NRT,HND 2026-11-01 2026-11-15 --cabin business --cheapest
  ./seats.py search DFW LHR,CDG,FRA 2027-03-01 2027-06-30 --cabin business --points bilt,citi --max-miles 80000 --min-seats 2
  ./seats.py bulk aeroplan "North America" Europe --cabin business --start 2027-03-01 --end 2027-06-30 --origins DFW,IAH
  ./seats.py trips <availability-id> --cabin business
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://seats.aero/partnerapi"
CABINS = {"economy": "Y", "premium": "W", "business": "J", "first": "F"}
REGIONS = ["North America", "South America", "Africa", "Asia", "Europe", "Oceania"]

# seats.aero sources reachable from each transferable currency. Partner lists change;
# confirm on the card issuer's site before transferring.
POINTS = {
    "bilt": ["aeroplan", "flyingblue", "united", "virginatlantic", "turkish", "emirates", "qatar", "alaska"],
    "citi": ["flyingblue", "virginatlantic", "turkish", "qatar", "emirates", "etihad", "singapore",
             "qantas", "aeromexico", "jetblue", "american"],
    "amex": ["aeroplan", "flyingblue", "virginatlantic", "delta", "qatar", "emirates", "etihad",
             "singapore", "qantas", "aeromexico", "jetblue"],
}

quota_remaining = None


def load_key():
    key = os.environ.get("SEATS_AERO_API_KEY")
    env = Path(__file__).with_name(".env")
    if not key and env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("SEATS_AERO_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
            elif line and "=" not in line and not key:
                key = line  # bare key on its own line
    if not key:
        sys.exit("Missing API key: set SEATS_AERO_API_KEY or put it in a .env file next to seats.py")
    return key


def get(path, params):
    global quota_remaining
    params = {k: v for k, v in params.items() if v is not None}
    url = f"{BASE}/{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={
        "Partner-Authorization": load_key(),
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            quota_remaining = resp.headers.get("x-ratelimit-remaining", quota_remaining)
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")


def fetch_pages(path, params, max_pages):
    """Follow cursor/skip pagination; each page is one API call."""
    rows, cursor = [], None
    for _ in range(max_pages):
        page = get(path, {**params, "take": 1000, "cursor": cursor, "skip": len(rows) or None})
        rows.extend(page.get("data", []))
        if not page.get("hasMore"):
            break
        cursor = page.get("cursor")
    return rows


def resolve_sources(args):
    sources = set(filter(None, (args.sources or "").split(",")))
    for currency in filter(None, (args.points or "").split(",")):
        if currency not in POINTS:
            sys.exit(f"Unknown --points value {currency!r}; choose from {', '.join(POINTS)}")
        sources.update(POINTS[currency])
    return sources


def fmt_taxes(cents, currency):
    if not cents:
        return ""
    amount = cents / 100
    return f"${amount:,.0f}" if currency in (None, "", "USD") else f"{amount:,.0f} {currency}"


def flatten(rows, args, sources=None):
    """One output row per (availability, cabin) that passes the filters."""
    codes = [CABINS[args.cabin]] if args.cabin else ["Y", "W", "J", "F"]
    origins = set(filter(None, (getattr(args, "origins", None) or "").upper().split(",")))
    dests = set(filter(None, (getattr(args, "dests", None) or "").upper().split(",")))
    out = []
    for r in rows:
        route = r.get("Route", {})
        if sources and r.get("Source") not in sources:
            continue
        if origins and route.get("OriginAirport") not in origins:
            continue
        if dests and route.get("DestinationAirport") not in dests:
            continue
        for c in codes:
            if not r.get(f"{c}Available"):
                continue
            direct_only = getattr(args, "direct", False)
            prefix = f"{c}Direct" if direct_only else c
            if direct_only and not r.get(f"{c}Direct"):
                continue
            miles = int(r.get(f"{prefix}MileageCost") or r.get(f"{c}MileageCost") or 0)
            seats = r.get(f"{prefix}RemainingSeats") or r.get(f"{c}RemainingSeats") or 0
            if args.max_miles and miles > args.max_miles:
                continue
            # 0 seats on an available cabin means the program doesn't report counts
            if args.min_seats and seats and seats < args.min_seats:
                continue
            if args.min_seats and not seats and args.strict_seats:
                continue
            out.append({
                "date": r["Date"],
                "route": f"{route.get('OriginAirport')}-{route.get('DestinationAirport')}",
                "program": r.get("Source"),
                "cabin": c,
                "miles": miles,
                "taxes": fmt_taxes(r.get(f"{prefix}TotalTaxes") or r.get(f"{c}TotalTaxes"), r.get("TaxesCurrency")),
                "seats": seats or "?",
                "airlines": r.get(f"{prefix}Airlines") or r.get(f"{c}Airlines") or "",
                "direct": "yes" if r.get(f"{c}Direct") else "",
                "id": r["ID"],
            })
    return out


def print_table(out, args, raw_count):
    if args.json:
        json.dump(out, sys.stdout, indent=2)
        return
    out.sort(key=(lambda x: (x["miles"], x["date"])) if args.cheapest else (lambda x: (x["date"], x["miles"])))
    if not out:
        print(f"No availability found ({raw_count} raw results).")
    else:
        cols = ["date", "route", "program", "cabin", "miles", "taxes", "seats", "airlines", "direct", "id"]
        shown = out[: args.limit]
        widths = {c: max(len(c), *(len(str(o[c])) for o in shown)) for c in cols}
        print("  ".join(c.upper().ljust(widths[c]) for c in cols))
        for o in shown:
            print("  ".join(str(o[c]).ljust(widths[c]) for c in cols))
        if len(out) > args.limit:
            print(f"... {len(out) - args.limit} more (use --limit)")
    print(f"[API calls left today: {quota_remaining}]", file=sys.stderr)


def search(args):
    sources = resolve_sources(args)
    params = {
        "origin_airport": args.origin.upper(),
        "destination_airport": args.destination.upper(),
        "start_date": args.start,
        "end_date": args.end or args.start,
        "cabins": args.cabin,
        "sources": ",".join(sorted(sources)) or None,
        "carriers": args.carriers,
        "only_direct_flights": "true" if args.direct else None,
        "order_by": "lowest_mileage" if args.cheapest else None,
        "min_cabin_pct": args.min_cabin_pct,
    }
    rows = fetch_pages("search", params, args.max_pages)
    print_table(flatten(rows, args), args, len(rows))


def bulk(args):
    params = {
        "source": args.source,
        "cabin": args.cabin,
        "origin_region": args.origin_region,
        "destination_region": args.destination_region,
        "start_date": args.start,
        "end_date": args.end,
        "min_cabin_pct": args.min_cabin_pct,
    }
    rows = fetch_pages("availability", params, args.max_pages)
    print_table(flatten(rows, args), args, len(rows))


def verify(ids, cabin, min_seats=None, max_miles=None, max_taxes=None):
    """Fetch flight-level trips for availability ids (one API call each) and keep only
    itineraries that meet the filters. Summary rows mix seats/taxes across itineraries,
    so this is the step that tells you what's actually bookable together."""
    keep = []
    for aid in ids:
        data = get(f"trips/{aid}", {})
        links = [l.get("link") for l in data.get("booking_links", []) if l.get("primary")] or \
                [l.get("link") for l in data.get("booking_links", [])[:1]]
        for t in data.get("data", []):
            if cabin and t.get("Cabin") != cabin:
                continue
            seats = t.get("RemainingSeats") or 0
            if min_seats and seats and seats < min_seats:
                continue
            if max_miles and (t.get("MileageCost") or 0) > max_miles:
                continue
            if max_taxes is not None and (t.get("TaxesCurrency") in (None, "", "USD")) \
                    and (t.get("TotalTaxes") or 0) > max_taxes * 100:
                continue
            t["_link"] = links[0] if links else ""
            keep.append(t)
    return keep


def describe_trip(t):
    taxes = fmt_taxes(t.get("TotalTaxes"), t.get("TaxesCurrency")) or "taxes n/a"
    dur = t.get("TotalDuration") or 0
    segs = t.get("AvailabilitySegments", [])
    legs = "  ".join(f"{s.get('FlightNumber')} {s.get('OriginAirport')}-{s.get('DestinationAirport')} "
                     f"{s.get('DepartsAt', '')[5:16].replace('T', ' ')}" for s in segs)
    return (f"{segs[0].get('DepartsAt', '')[:10] if segs else '?'}  {t.get('Source'):13} {t.get('Cabin'):8} "
            f"{t.get('MileageCost'):>6} + {taxes:9} seats={t.get('RemainingSeats') or '?':<2} "
            f"{dur // 60}h{dur % 60:02d}m  {legs}")


def trips(args):
    data = get(f"trips/{args.id}", {"min_cabin_pct": args.min_cabin_pct})
    if args.json:
        json.dump(data, sys.stdout, indent=2)
        return
    trip_list = data.get("data", [])
    if args.cabin:
        trip_list = [t for t in trip_list if t.get("Cabin") == args.cabin]
    trip_list.sort(key=lambda t: (t.get("MileageCost") or 0, t.get("TotalDuration") or 0))
    if not trip_list:
        print("No matching trips.")
    for t in trip_list:
        taxes = fmt_taxes(t.get("TotalTaxes"), t.get("TaxesCurrency"))
        print(f"\n{t.get('Cabin', '').upper()}  {t.get('MileageCost')} miles{' + ' + taxes if taxes else ''}  "
              f"seats={t.get('RemainingSeats') or '?'}  stops={t.get('Stops')}  "
              f"{t.get('TotalDuration', 0) // 60}h{t.get('TotalDuration', 0) % 60:02d}m")
        for s in t.get("AvailabilitySegments", []):
            print(f"   {s.get('FlightNumber'):<8} {s.get('OriginAirport')}->{s.get('DestinationAirport')}  "
                  f"{s.get('DepartsAt', '')[:16]} -> {s.get('ArrivesAt', '')[:16]}  "
                  f"{s.get('AircraftName', '')}  fare={s.get('FareClass', '')}")
    for link in data.get("booking_links", []):
        print(f"\nBook: {link.get('label')}: {link.get('link')}")


def add_filters(p):
    p.add_argument("--cabin", choices=CABINS.keys())
    p.add_argument("--max-miles", type=int)
    p.add_argument("--min-seats", type=int, help="programs that don't report seat counts show '?' and are kept")
    p.add_argument("--strict-seats", action="store_true", help="with --min-seats, drop rows with unknown seat counts")
    p.add_argument("--direct", action="store_true", help="nonstop only")
    p.add_argument("--min-cabin-pct", type=int, help="0-100; lower allows mixed-cabin itineraries")
    p.add_argument("--cheapest", action="store_true", help="sort by miles instead of date")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--max-pages", type=int, default=3, help="each page (1000 rows) costs one API call")
    p.add_argument("--json", action="store_true")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="cached search across programs for specific airports")
    s.add_argument("origin", help="origin airport(s), comma-separated")
    s.add_argument("destination", help="destination airport(s), comma-separated")
    s.add_argument("start", help="start date YYYY-MM-DD")
    s.add_argument("end", nargs="?", help="end date YYYY-MM-DD (defaults to start)")
    s.add_argument("--sources", help="mileage programs, e.g. aeroplan,alaska,united")
    s.add_argument("--points", help=f"expand to programs reachable from: {', '.join(POINTS)}")
    s.add_argument("--carriers", help="operating airlines, e.g. NH,JL")
    add_filters(s)
    s.set_defaults(func=search)

    b = sub.add_parser("bulk", help="everything one program has between two regions")
    b.add_argument("source", help="one mileage program, e.g. aeroplan")
    b.add_argument("origin_region", choices=REGIONS)
    b.add_argument("destination_region", choices=REGIONS)
    b.add_argument("--start", help="start date YYYY-MM-DD")
    b.add_argument("--end", help="end date YYYY-MM-DD")
    b.add_argument("--origins", help="keep only these origin airports (client-side filter)")
    b.add_argument("--dests", help="keep only these destination airports (client-side filter)")
    add_filters(b)
    b.set_defaults(func=bulk)

    t = sub.add_parser("trips", help="flight-level details for an availability id")
    t.add_argument("id")
    t.add_argument("--cabin", choices=CABINS.keys())
    t.add_argument("--min-cabin-pct", type=int)
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=trips)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
