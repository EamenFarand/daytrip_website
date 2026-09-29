# Phase 0 audit — scripts

Findings are in [REPORT.md](REPORT.md), and the master table is [stations.csv](stations.csv).

## Run

```bash
cd audit
uv sync
uv run python run_all.py      # regenerates everything, including stations.csv
uv run pytest                 # parser tests
```

Downloads are cached in `../data/raw/` (git-ignored) and only re-fetched when the server says they changed. The first run downloads about 260 MB (mostly the GTFS feed).

## Scripts

| Script | Answers | What it does |
|---|---|---|
| `fetch.py` | – | Polite cached downloads: identifying User-Agent, conditional GET, at most 1 request/s |
| `gtfs_rail.py` | Q1, Q2 | Rail routes → trips → platform stops → parent stations from the OVapi GTFS feed |
| `epiap.py` | Q3, Q4, Q5 | Parses DOVA's NeTEx EPIAP export: per-track step-free flags, lifts, which tracks each lift serves |
| `topology.py` | Q4 | Checks whether EPIAP's walking links connect every track to a street entrance |
| `sources_misc.py` | Q3, Q6 | NS IFF station attributes, the ProRail 2020 step-free list, track heights, lift/ramp register |
| `osm.py` | Q3, Q6 | One Overpass query for stations and elevators (cached 7 days) |
| `build_stations.py` | Q1, Q6 | Joins all sources on NS station code into `stations.csv`, with a `recommended_status` column |
| `lift_listener.py` | Q5 | Logs the live SIRI-FM lift feed (ZeroMQ) to `data/raw/lifts/*.jsonl`; run separately, e.g. `uv run python lift_listener.py 72` |

## `stations.csv` columns

- `recommended_status`: yes / partial / no / unknown. This is EPIAP, set to *unknown* where evidence conflicts (see `review_reason`).
- `epiap_*`: EPIAP counts per station (tracks true/false/unknown, lifts, ramps, path links) and `topology_via_halls`.
- `reg_*`: ProRail asset register (June 2026): lifts, lift status (`VRIJ` = in use, `PROJ` = project), ramps.
- `gtfs_wb_*`: GTFS `wheelchair_boarding`. `ns_tgst_status` / `ns_rast`: NS IFF attributes "station toegankelijk" / travel assistance.
- `pr2020_*`: ProRail's step-free map input, 2019–2020.
- `osm_*`: OpenStreetMap `wheelchair` tag and elevators within 250 m.
- `pr_boarding_*`: ProRail per-track boarding height (Q2 2026). This is about getting into the train, not reaching the platform.
