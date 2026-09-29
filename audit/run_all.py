"""Regenerate every audit output from scratch: `uv run python run_all.py`.

Downloads are cached in data/raw/ (conditional requests), so re-runs are cheap.
The live lift listener is not part of this; run lift_listener.py separately.
"""

from __future__ import annotations

import warnings

import build_stations
import epiap
import gtfs_rail
import osm
import sources_misc
import topology

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

STEPS = [
    ("GTFS rail network (Q1, Q2)", gtfs_rail.main),
    ("EPIAP station accessibility (Q3, Q4)", epiap.main),
    ("EPIAP topology connectivity (Q4)", topology.main),
    ("NS IFF + ProRail files (Q3, Q6)", sources_misc.main),
    ("OpenStreetMap (Q3, Q6)", osm.main),
    ("Master station table (Q1, Q6)", build_stations.main),
]

if __name__ == "__main__":
    for name, step in STEPS:
        print(f"== {name}")
        step()
