# Seats Aero Atlas

Award-flight availability from your home airport, as one interactive page.

Seats Aero Atlas pulls cached award availability from the [seats.aero](https://seats.aero) Partner API, keeps only what fits your rules (cabin, number of travelers, points you can transfer, stops, price caps), and builds a single HTML page with:

- **a spinnable globe** of every route, colored by value, with dashed lines for separate positioning flights;
- **a points-vs-cash chart**: drag a box to keep only the options inside it;
- **filters** for direction, region, route type, points currency, price, taxes & surcharges and travel dates;
- **a table grouped by continent and city**, showing each itinerary's full path (`DFW ┄→ ORD → MUC/FRA → LIS`), the aircraft, a day-by-day strip of availability and price, and links to each airline's award search and to seats.aero for every date.

## Requirements

- Python 3.9+ (standard library only)
- A [seats.aero Pro](https://seats.aero/pro) membership with Partner API access. Pro keys allow 1,000 API calls a day; a full refresh with the example config uses roughly 100–250.

## Setup

```bash
git clone <this repo> seats-aero-atlas && cd seats-aero-atlas
cp .env.example .env                    # then paste your key from seats.aero → Settings → API
cp config.example.json config.json      # then edit it (see below)
./run.sh
open dist/index.html
```

`.env`, `config.json`, `data/` and `dist/` are git-ignored, so your key, your personal settings and the seats.aero data stay on your machine.

## Configuration (`config.json`)

| Key | What it does |
|---|---|
| `home` | Home airport code, display names, nearby airports (`metro`) and coordinates for the globe. |
| `travelers` | Seats needed. Options with fewer reported seats are dropped; totals multiply by this. |
| `cabin` | `economy`, `premium`, `business` or `first`. |
| `start_date`, `end_date` | Travel window to search. |
| `currencies` | Your transferable points and the seats.aero programs each one reaches. Only these programs are searched, and the page's "Points you have" filter uses them. Transfer partners change; check your card issuer. |
| `exclude_airports` | Airports to leave out as origins or destinations. |
| `region_overrides` | Relabel airports into your own region (seats.aero files the Middle East under Asia). |
| `tiers` | Per-person points and taxes & surcharges limits for the gold/blue/gray coloring. |
| `page` | Title, headline text and defaults for the sliders and direction toggle. `{home_name}`, `{start}`, `{last}`, `{travelers_word}`, `{pulled}` and friends are filled in for you. |
| `airport_groups` | Named airport lists, referenced in searches as `@NAME` (`@HOME` is your home airport). |
| `searches` | What to ask seats.aero. Each has a `direction` (`out` or `ret`), `origins`, `destinations`, `max_stops`, a points `cap` per person, and paging: `pages` (1,000 results = 1 API call each) and `stop_above` (stop paging once a whole page costs more than this). |

An itinerary that starts or ends at home is **one ticket from home**. Anything else is a **gateway** itinerary: the page shows the separate positioning flight as a dashed leg.

The globe's region views are tuned for a home airport in North America; the region buttons follow seats.aero's regions plus any `region_overrides`.

## Commands

```bash
./run.sh                    # full refresh: search, build, look up connections, write dist/index.html
./run.sh --build            # rebuild the page from saved data (no API calls)
python3 -m atlas.search gw_europe_out gw_europe_ret   # re-run only some searches
python3 -m atlas.compare                 # what changed since the previous run
python3 -m atlas.compare CAI IST         # ...only for routes touching these airports
python3 -m atlas.window 2027-09-22 2027-09-24 --to JFK,EWR,DFW   # best flights for specific dates
./seats.py search DFW LHR,CDG 2027-09-01 2027-09-30 --cabin business --points bilt --min-seats 2
```

`seats.py` is also a small standalone CLI for ad-hoc searches (`search`, `bulk`, `trips`).

## How it works

| Step | File | Output |
|---|---|---|
| Search | `atlas/search.py` | `data/raw/<search>.json`: raw `/search` results with flight-level trips |
| Filter and group | `atlas/build_data.py` | `data/options.json`: one row per route × program × airline × stops, with its dates |
| Connections | `atlas/segments.py` | Calls `/trips` for flights whose route isn't cached yet (`data/segments.json`) and tags each 1-stop date with where it connects, flagging airport changes |
| Page | `atlas/build_page.py` + `web/template.html` | `dist/index.html`: a single self-contained page (d3 and topojson load from a CDN) |

## Data and terms

Availability comes from seats.aero. Their [terms](https://seats.aero/terms) allow personal, non-commercial use of the API **with visible attribution to seats.aero** (the generated page credits seats.aero), and require written permission for commercial use. This repository contains only code: it doesn't include or redistribute seats.aero data. Check with seats.aero before publishing generated pages or data.

Award availability is cached and can be stale. Always confirm on the airline's site before transferring points; transfers can't be undone.

## Credits

- Data: [seats.aero](https://seats.aero)
- Map: [world-atlas](https://github.com/topojson/world-atlas) country outlines (ISC), from Natural Earth
- Charts and globe: [d3](https://d3js.org) and [topojson-client](https://github.com/topojson/topojson-client) (ISC)

## License

MIT. See [LICENSE](LICENSE).
