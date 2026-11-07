#!/usr/bin/env bash
# Full refresh: search seats.aero, build the options, find connections, and write dist/index.html.
# Usage: ./run.sh            run everything (about 25-60 API calls per search, of 1,000 a day)
#        ./run.sh --build    rebuild the page from the data already saved, no API calls
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
[ -f data/options.json ] && cp data/options.json data/options_prev.json
if [ "${1:-}" != "--build" ]; then
  $PY -m atlas.search
fi
$PY -m atlas.build_data
if [ "${1:-}" != "--build" ]; then
  $PY -m atlas.segments 300
else
  $PY -m atlas.segments 0
fi
$PY -m atlas.build_page
echo "Open dist/index.html in a browser. Compare with the last run: $PY -m atlas.compare"
