"""Best award flights for a specific trip window, straight from the raw search data (every program,
every flight combination), with room for the configured number of travelers.

Examples:
  python -m atlas.window 2027-09-22 2027-09-24 --to JFK,EWR,DFW
  python -m atlas.window 2027-09-12 2027-09-15 --from DFW --max-tax 300
  python -m atlas.window 2027-09-20 2027-09-25 --from MAD,BCN,LIS --max-points 90000
"""
import argparse
import json

from atlas.config import RAW, CABIN, TRAVELERS

FX = {"USD": 1, "CAD": .73, "EUR": 1.08, "GBP": 1.27, "AUD": .66, "AED": .27, "XPF": .0091, "SAR": .27, "SGD": .74}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("start"); p.add_argument("end")
    p.add_argument("--from", dest="orig", help="origin airports, comma-separated")
    p.add_argument("--to", dest="dest", help="destination airports, comma-separated")
    p.add_argument("--max-tax", type=float, default=500, help="taxes & surcharges per person, USD (default 500)")
    p.add_argument("--max-points", type=int, default=130000)
    p.add_argument("--limit", type=int, default=40)
    a = p.parse_args()
    orig = set(a.orig.upper().split(",")) if a.orig else None
    dest = set(a.dest.upper().split(",")) if a.dest else None
    best = {}
    for f in RAW.glob("*.json"):
        for r in json.loads(f.read_text()):
            if not (a.start <= r["Date"] <= a.end):
                continue
            for t in r.get("AvailabilityTrips") or []:
                if t.get("Cabin") != CABIN or (orig and t["OriginAirport"] not in orig) or (dest and t["DestinationAirport"] not in dest):
                    continue
                seats_left = t.get("RemainingSeats") or 0          # 0 = not reported (e.g. American)
                if seats_left and seats_left < TRAVELERS:
                    continue
                tax = round((t.get("TotalTaxes") or 0) / 100 * FX.get(r.get("TaxesCurrency") or "USD", 1))
                if tax > a.max_tax or t["MileageCost"] > a.max_points:
                    continue
                k = (t["OriginAirport"], t["DestinationAirport"], t["Source"], t.get("FlightNumbers"))
                best.setdefault(k, {})[r["Date"][5:]] = (t["MileageCost"], tax, seats_left or "?")
    rows = []
    for k, by_date in best.items():
        m, tax = min((v[0], v[1]) for v in by_date.values())
        dates = [f"{d}({v[2]})" for d, v in sorted(by_date.items()) if v[0] == m]
        rows.append((m + tax * 60, k, m, tax, dates))   # rank: points, with $1 of surcharges ~ 60 points
    for _, (o, d, src, fl), m, tax, dates in sorted(rows)[:a.limit]:
        print(f"{o}→{d}  {src:14} {fl:26} {m:>7,} + ${tax:<5} dates(seats) {', '.join(dates)}")
    if not rows:
        print("Nothing matches. Widen the dates, airports or caps, or refresh the data.")


if __name__ == "__main__":
    main()
