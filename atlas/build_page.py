"""Assemble dist/index.html: the page template + options data + world outlines + settings from config.json."""
import datetime
import json

from atlas.config import CFG, DATA, DIST, WEB, CABIN, TRAVELERS

WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

opts = (DATA / "options.json").read_text()
rows = json.loads(opts)
start = datetime.date.fromisoformat(CFG["start_date"])
last = datetime.date.fromisoformat(max(e["d"] for r in rows for e in r["dates"]))
label = lambda d: d.strftime("%b %-d")
pulled = datetime.date.today().strftime("%b %-d, %Y")
page, home, tiers = CFG.get("page", {}), CFG["home"], CFG.get("tiers", {})
best_pp, good_pp = tiers.get("best_pp", 60000), tiers.get("good_pp", 87500)
kfmt = lambda n: f"{n / 1000:g}k"

meta = {
    "start": CFG["start_date"], "last": last.isoformat(), "pulled": pulled,
    "home": home, "travelers": TRAVELERS, "cabin": CABIN,
    "currencies": CFG["currencies"], "defaultDir": page.get("default_direction", "out"),
    "tiers": {"bestPP": best_pp, "bestTax": tiers.get("best_tax", 300),
              "goodPP": good_pp, "goodTax": tiers.get("good_tax", 800)},
    "maxDefault": page.get("default_max_points", 100000), "maxCap": page.get("max_points_slider", 130000),
}
fill = {
    "start": label(start), "last": label(last), "year": str(start.year), "pulled": pulled,
    "home": home["code"], "home_name": home["name"], "home_short": home.get("short", home["name"]),
    "travelers": str(TRAVELERS), "travelers_word": WORDS.get(TRAVELERS, str(TRAVELERS)),
}
replacements = {
    "__OPTIONS_JSON__": opts,
    "__WORLD_JSON__": (WEB / "countries-110m.json").read_text(),
    "__META_JSON__": json.dumps(meta),
    "__TITLE__": page.get("title", f"{home['code']} Award Atlas"),
    "__EYEBROW__": page.get("eyebrow", "{cabin} class · {travelers} travelers").format(cabin=CABIN.title(), **fill),
    "__LEDE__": page.get("lede", "").format(**fill),
    "__START_LABEL__": fill["start"], "__LAST_LABEL__": fill["last"],
    "__DMAX__": str((last - start).days), "__PULLED__": pulled,
    "__HOME_NAME__": fill["home_name"], "__HOME_SHORT__": fill["home_short"], "__HOME__": fill["home"],
    "__N_WORD__": fill["travelers_word"], "__N__": fill["travelers"],
    "__BEST_TOTAL__": kfmt(best_pp * TRAVELERS), "__GOOD_TOTAL__": kfmt(good_pp * TRAVELERS),
    "__BEST_TAX__": str(meta["tiers"]["bestTax"]), "__GOOD_TAX__": str(meta["tiers"]["goodTax"]),
    "__MAX_DEFAULT__": str(meta["maxDefault"]), "__MAX_CAP__": str(meta["maxCap"]),
    "__MAX_DEFAULT_LABEL__": f"{meta['maxDefault']:,}", "__MAX_CAP_K__": kfmt(meta["maxCap"]),
}
out = (WEB / "template.html").read_text()
for k, v in replacements.items():   # order matters: longer placeholders (__HOME_NAME__) before __HOME__
    out = out.replace(k, v)
(DIST / "index.html").write_text(out)
print(f"built dist/index.html, {len(out):,} bytes; dates {label(start)} to {label(last)}; pulled {pulled}")
