"""Loads config.json and resolves the paths every pipeline step shares."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import seats  # noqa: E402  (the API client lives at the repo root)

CONFIG_PATH = Path(os.environ.get("ATLAS_CONFIG", ROOT / "config.json"))
if not CONFIG_PATH.exists():
    sys.exit(f"Missing {CONFIG_PATH.name}: copy config.example.json to config.json and edit it.")
CFG = json.loads(CONFIG_PATH.read_text())

DATA = ROOT / "data"
RAW = DATA / "raw"
DIST = ROOT / "dist"
WEB = ROOT / "web"
for d in (RAW, DIST):
    d.mkdir(parents=True, exist_ok=True)

HOME = CFG["home"]["code"]
TRAVELERS = CFG.get("travelers", 2)
CABIN = CFG.get("cabin", "business")
GROUPS = CFG.get("airport_groups", {})
# Programs searched: every seats.aero source reachable from the currencies listed in config.
SOURCES = sorted({p for progs in CFG["currencies"].values() for p in progs})


def airports(spec):
    """Expand a list like ["@HOME", "@EUROPE", "LIS"] into a comma-separated airport string."""
    out = []
    for item in spec:
        if item == "@HOME":
            out.append(HOME)
        elif item.startswith("@"):
            out.extend(GROUPS[item[1:]])
        else:
            out.append(item)
    return ",".join(dict.fromkeys(out))


def load(name):
    return json.loads((DATA / name).read_text())


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, separators=(",", ":")))
