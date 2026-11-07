"""What changed since the last refresh: data/options_prev.json vs data/options.json.

Usage: python -m atlas.compare [AIRPORT ...]   (airports narrow the report to routes touching them)
"""
import sys

from atlas.config import DATA, load

FX = {"USD": 1, "CAD": .73, "EUR": 1.08, "GBP": 1.27, "JPY": .0068, "AUD": .66, "XPF": .0091, "FJD": .44,
      "AED": .27, "SAR": .27, "SGD": .74}
usd = lambda e: e["t"] * FX.get(e["c"], 1)
key = lambda r: (r["dir"], r["o"], r["d"], r["prog"], r["ops"], r["stops"])


def summ(r):
    m = min(e["m"] for e in r["dates"])
    low = [e for e in r["dates"] if e["m"] == m]
    return m, min(usd(e) for e in low), len(r["dates"]), sorted(e["d"] for e in r["dates"])


def line(r):
    m, tax, n, ds = summ(r)
    return (f"{r['dir']:3} {r['kind']:4} {r['o']}-{r['d']} {r['prog']:14} {r['ops']:8} s{r['stops']} "
            f"{m:>7,} pp ${tax:,.0f} {n} dates ({ds[0][5:]}..{ds[-1][5:]})")


def main(focus):
    if not (DATA / "options_prev.json").exists():
        sys.exit("No previous snapshot yet (data/options_prev.json); run the pipeline twice.")
    prev, new = load("options_prev.json"), load("options.json")
    keep = (lambda r: r["o"] in focus or r["d"] in focus) if focus else (lambda r: True)
    prev, new = [r for r in prev if keep(r)], [r for r in new if keep(r)]
    P, N = {key(r): r for r in prev}, {key(r): r for r in new}
    print(f"options: {len(prev)} -> {len(new)} | route-dates: "
          f"{sum(len(r['dates']) for r in prev)} -> {sum(len(r['dates']) for r in new)}")
    if new:
        print(f"latest date: {max((e['d'] for r in prev for e in r['dates']), default='-')} -> "
              f"{max(e['d'] for r in new for e in r['dates'])}")
    gone, came = [P[k] for k in P if k not in N], [N[k] for k in N if k not in P]
    print(f"\n== route/program combos gone: {len(gone)}, new: {len(came)}")
    for label, rows in (("GONE", gone), ("NEW ", came)):
        for r in sorted(rows, key=lambda r: min(e["m"] for e in r["dates"]))[:20]:
            print(f"  {label} {line(r)}")
    print("\n== lowest price changed (per person)")
    ch = sorted(((summ(N[k])[0] - summ(P[k])[0], k) for k in P.keys() & N.keys()), key=lambda x: x[0])
    for delta, k in [c for c in ch if c[0]][:25]:
        a, b = summ(P[k]), summ(N[k])
        print(f"  {k[0]} {k[1]}-{k[2]} {k[3]:14} {k[4]:8} {a[0]:>7,} -> {b[0]:>7,} ({delta:+,}); dates {a[2]} -> {b[2]}")
    print("\n== biggest changes in number of dates")
    dc = sorted(((summ(N[k])[2] - summ(P[k])[2], k) for k in P.keys() & N.keys()), key=lambda x: x[0])
    for d, k in dc[:10] + dc[-10:]:
        if d:
            print(f"  {k[0]} {k[1]}-{k[2]} {k[3]:14} {k[4]:8} {summ(P[k])[2]} -> {summ(N[k])[2]} dates ({d:+})")


if __name__ == "__main__":
    main({a.upper() for a in sys.argv[1:]})
