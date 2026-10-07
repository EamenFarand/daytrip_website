"""Paths, sources and routing rules in one place.

Routing choices here are explained in docs/DECISIONS.md; change them there too.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OVERRIDES = Path(__file__).resolve().parents[1] / "overrides" / "stations.csv"


def env(key: str) -> str | None:
    """Read a setting from the environment, falling back to the git-ignored .env file."""
    if os.environ.get(key):
        return os.environ[key]
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key and v.strip() and not k.strip().startswith("#"):
                return v.strip()
    return None


# Locally both live outside the repo (see .env), so Nextcloud doesn't sync or lock them.
# In CI they are data/raw and data/build.
CACHE = Path(env("STEPFREE_CACHE") or ROOT / "data" / "raw")
BUILD = Path(env("STEPFREE_BUILD") or ROOT / "data" / "build")

USER_AGENT = "trapvrij/0.1 (+https://trapvrij.nl; https://github.com/EamenFarand/daytrip_website)"

# Sources
GTFS_URL = "http://gtfs.ovapi.nl/nl/gtfs-nl.zip"
EPIAP_DIR = "https://data.ndovloket.nl/netex/epiap/"
IFF_URL = "https://data.ndovloket.nl/ns/ns-latest.zip"

# Trip planning window: departures from the origin between these times (minutes after midnight).
WINDOW_START = 8 * 60 + 30
WINDOW_END = 12 * 60
MAX_TRANSFERS = 2  # results for 0, 1 and 2 changes
LATEST_ARRIVAL = 20 * 60  # ignore journeys arriving later than this (day trips)

# Transfers
STROLLER_BUFFER = 3  # extra minutes on top of the normal minimum transfer time
DEFAULT_TRANSFER = 2  # fallback when NS lists 0 minutes for a station
MIN_SAME_PLATFORM = 2  # re-boarding on the same platform or across an island platform

# Trips we never route on: buses in the rail feed, heritage lines, and trains that
# need their own ticket or a reservation (not usable with a normal day-trip ticket).
EXCLUDED_AGENCIES = {"Miljoenenlijn"}
EXCLUDED_CATEGORIES = {"Drempelvrije bus", "Eurostar", "European Sleeper", "GoVolta", "Nightjet"}

# "Sprinter" train set: trains without steps inside or at the door (Daan, 2026-09-29, option A).
# First NS's own mark per train, from recent weeks (trains.py, DECISIONS 2026-10-07); without one, the category:
# NS only Sprinters, regional and cross-border stopping-train operators every train they run.
SPRINTER_NS_CATEGORIES = {"Sprinter"}
NS_AGENCIES = {"NS", "NS International"}

TRAIN_SETS = ("all", "sprinter")
PROFILES = ("any", "stroller")
DAY_TYPES = ("weekday", "saturday")


def in_train_set(agency: str, category: str | None, train_set: str, step_free: bool | None = None) -> bool:
    """`step_free`: NS's verdict for this train (trains.verdicts), or None when there isn't one."""
    if agency in EXCLUDED_AGENCIES or category in EXCLUDED_CATEGORIES:
        return False
    if train_set == "all":
        return True
    if step_free is not None:
        return step_free
    if agency in NS_AGENCIES:
        return category in SPRINTER_NS_CATEGORIES
    return True  # Arriva, Keolis, Qbuzz, R-net NS, DB, Eurobahn, VIAS, NMBS stopping trains


def by_category(agency: str, category: str | None) -> bool:
    """Would the category alone put this train in the "sprinter" set? (An intercity NS marks accessible wouldn't.)"""
    return in_train_set(agency, category, "sprinter")
