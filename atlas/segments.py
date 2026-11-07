"""Find where each 1-stop itinerary connects.

Search results list flight numbers but not the connecting airport, so this calls /trips for flights
whose route isn't known yet and caches the answer in data/segments.json ("FLIGHT|date" -> [from, to]).
Then every 1-stop date in options.json gets "v" (the airport the first flight lands at) and, when the
second flight leaves from another airport in the same city, "vx" (an airport change).

Usage: python -m atlas.segments [max_trips_calls]   (default 150)
"""
import json
import socket
import sys
import time
from collections import Counter, defaultdict

from atlas.config import DATA, RAW, load, save, seats

# A ticketed connection can only switch airports within one city; other mismatches are stale flight-number data.
METROS = [{"JFK", "LGA", "EWR"}, {"IAD", "DCA", "BWI"}, {"LHR", "LGW", "LCY", "STN"}, {"LAX", "ONT", "BUR", "SNA", "LGB"},
          {"ORD", "MDW"}, {"IAH", "HOU"}, {"CDG", "ORY"}, {"NRT", "HND"}, {"GRU", "CGH", "VCP"}, {"EZE", "AEP"},
          {"GIG", "SDU"}, {"DFW", "DAL"}, {"MIA", "FLL"}, {"SFO", "OAK", "SJC"}]
same_city = lambda a, b: any(a in m and b in m for m in METROS)


def flights(e):
    return [f.strip() for f in e["f"].split(",") if f.strip()]


def lookup(cap):
    path = DATA / "segments.json"
    by_day = json.loads(path.read_text())["by_day"] if path.exists() else {}
    routes = defaultdict(set)
    for k, (o, x) in by_day.items():
        routes[k.split("|")[0]].add((o, x))
    need = set()
    for r in load("options.json"):
        if r["stops"] != 1:
            continue
        for e in r["dates"]:
            fl = flights(e)
            if len(fl) < 2:
                continue
            if not any(rt[0] == r["o"] for rt in routes.get(fl[0], ())): need.add(fl[0])
            if not any(rt[1] == r["d"] for rt in routes.get(fl[1], ())): need.add(fl[1])
    # Which availability ids cover the unknown flights; pick the ids that resolve the most first.
    avail = defaultdict(set)
    for f in RAW.glob("*.json"):
        for r in json.loads(f.read_text()):
            for t in r.get("AvailabilityTrips") or []:
                for fn in (t.get("FlightNumbers") or "").split(","):
                    if fn.strip() in need:
                        avail[t["AvailabilityID"]].add(fn.strip())
    left, calls = set(need), 0
    while left and calls < cap:
        best = max(avail, key=lambda a: len(avail[a] & left), default=None)
        if not best or not (avail[best] & left):
            break
        d = {"data": []}
        for _ in range(3):
            try:
                d = seats.get(f"trips/{best}", {})
                break
            except (socket.timeout, TimeoutError, OSError):
                time.sleep(5)
        calls += 1
        for t in d.get("data", []):
            for s in t.get("AvailabilitySegments", []):
                fn, o, x = s.get("FlightNumber"), s.get("OriginAirport"), s.get("DestinationAirport")
                if fn and o and x:
                    by_day[f"{fn}|{(s.get('DepartsAt') or '')[:10]}"] = [o, x]
                    left.discard(fn)
        avail.pop(best)
    path.write_text(json.dumps({"by_day": by_day}))
    print(f"flights to look up: {len(need)}, trips calls: {calls}, still unknown: {len(left)}, "
          f"calls left today: {seats.quota_remaining}")
    return by_day


def tag(by_day):
    """Flight numbers can fly different routes on different days, so each leg is matched to a route
    that fits the itinerary (first leg leaves the origin, second lands at the destination)."""
    routes = defaultdict(set)
    for k, (o, x) in by_day.items():
        routes[k.split("|")[0]].add((o, x))
    rows = load("options.json")
    stats, changes = Counter(), Counter()
    for r in rows:
        if r["stops"] != 1:
            continue
        for e in r["dates"]:
            e.pop("v", None); e.pop("vx", None)
            fl = flights(e)
            if len(fl) < 2:
                stats["unknown"] += 1; continue
            F = [rt for rt in routes.get(fl[0], ()) if rt[0] == r["o"]]
            G = [rt for rt in routes.get(fl[1], ()) if rt[1] == r["d"]]
            ex1, ex2 = by_day.get(f"{fl[0]}|{e['d']}"), by_day.get(f"{fl[1]}|{e['d']}")
            cands = [(f, g) for f in (F or [None]) for g in (G or [None]) if f or g]
            if not cands:
                stats["unknown"] += 1; continue
            f, g = max(cands, key=lambda p: (bool(p[0] and p[1] and p[0][1] == p[1][0]),
                                              (p[0] == ex1) + (p[1] == ex2)))
            arr = f[1] if f else g[0]
            dep = g[0] if g else arr
            if arr in (r["o"], r["d"]):
                stats["unknown"] += 1; continue
            e["v"] = arr
            stats["tagged"] += 1
            if dep != arr and dep not in (r["o"], r["d"]) and same_city(arr, dep):
                e["vx"] = dep
                changes[f"{arr}->{dep}"] += 1
    save("options.json", rows)
    print(dict(stats), "| airport changes:", dict(changes.most_common(6)))


if __name__ == "__main__":
    tag(lookup(int(sys.argv[1]) if len(sys.argv) > 1 else 150))
