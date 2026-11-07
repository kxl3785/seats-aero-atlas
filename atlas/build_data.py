"""Merge the raw searches into data/options.json: one row per route/program/airline/stops, with its dates.

Rules come from config.json: cabin, travelers (minimum seats), each search's direction, max stops and
points cap, airports to leave out, and region relabels (seats.aero files the Middle East under Asia).
An itinerary that starts or ends at home is "home" (one ticket); anything else is "pos" (a gateway
itinerary that needs a separate positioning flight).
"""
import json
from collections import defaultdict

from atlas.config import CFG, RAW, CABIN, TRAVELERS, save

HOME_AIRPORTS = set(CFG["home"].get("metro", [CFG["home"]["code"]]))
EXCLUDE = set(CFG.get("exclude_airports", []))
RELABEL = {a: region for region, codes in CFG.get("region_overrides", {}).items() for a in codes}


def short_ac(x):
    """'Boeing 787-9' -> '787-9', 'Airbus A321neo/Lr/Xlr' -> 'A321neo/LR/XLR'."""
    x = (x or "").replace("Boeing ", "").replace("Airbus ", "").replace("Bombardier ", "")
    return x.replace("neo/Lr/Xlr", "neo/LR/XLR").strip()


groups = defaultdict(dict)
for s in CFG["searches"]:
    path = RAW / f"{s['name']}.json"
    if not path.exists():
        print(f"skipping {s['name']}: no raw data yet")
        continue
    dirn, maxstops, cap = s["direction"], s.get("max_stops", 1), s.get("cap", 130000)
    for r in json.loads(path.read_text()):
        rt = r["Route"]
        far = rt["DestinationAirport"] if dirn == "out" else rt["OriginAirport"]
        region = RELABEL.get(far) or (rt["DestinationRegion"] if dirn == "out" else rt["OriginRegion"])
        for t in r.get("AvailabilityTrips") or []:
            if t.get("Cabin") != CABIN or t.get("Stops", 9) > maxstops or t["MileageCost"] > cap:
                continue
            o, d = t["OriginAirport"], t["DestinationAirport"]
            if o in EXCLUDE or d in EXCLUDE:
                continue
            seats_left = t.get("RemainingSeats") or 0   # 0 means the program doesn't report seat counts
            if seats_left and seats_left < TRAVELERS:
                continue
            kind = "home" if (o in HOME_AIRPORTS or d in HOME_AIRPORTS) else "pos"
            ops = ",".join(sorted({c.strip() for c in (t.get("Carriers") or "").split(",") if c.strip()}))
            key = (dirn, kind, region, o, d, t["Source"], ops, t["Stops"])
            entry = {"d": r["Date"], "m": t["MileageCost"], "s": seats_left or None,
                     "t": round((t.get("TotalTaxes") or 0) / 100), "c": r.get("TaxesCurrency") or "USD",
                     "f": t.get("FlightNumbers") or "", "dur": t.get("TotalDuration")}
            ac = t.get("Aircraft")
            if isinstance(ac, list) and ac:
                entry["a"] = " → ".join(short_ac(x) for x in ac)
            prev = groups[key].get(r["Date"])
            if prev is None or (entry["m"], entry["t"]) < (prev["m"], prev["t"]):
                groups[key][r["Date"]] = entry

rows = []
for (dirn, kind, region, o, d, src, ops, stops), bydate in groups.items():
    rows.append({"dir": dirn, "kind": kind, "region": region, "o": o, "d": d, "prog": src,
                 "ops": ops, "stops": stops, "dates": sorted(bydate.values(), key=lambda e: e["d"])})
rows.sort(key=lambda r: (r["dir"], min(e["m"] for e in r["dates"])))
save("options.json", rows)
print("options", len(rows), "route-dates", sum(len(r["dates"]) for r in rows))
