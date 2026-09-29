# Pipeline: router and precompute (Phase 1)

Builds everything the site loads. No AI at runtime, just this code.

```bash
cd pipeline
uv sync
uv run python -m stepfree.build          # ~2.5 min on 4 cores; downloads are cached
uv run pytest                            # 46 tests; the NS comparison skips until NS_API_KEY is set
uv run python -m stepfree.ns_check       # our journeys vs the NS journey planner (needs NS_API_KEY)
```

Options: `--today 2026-09-29` (reproducible day choice), `--only HTNC UT` (quick run for a few origins), `--workers 4`.

Locally, downloads and output live outside the repo, set in `.env` (`STEPFREE_CACHE`, `STEPFREE_BUILD`), so Nextcloud doesn't sync them. Without those settings (as in CI) they go to `data/raw/` and `data/build/`. Both are git-ignored.

## What it does

1. **Timetable** ([gtfs.py](stepfree/gtfs.py)): the OVapi GTFS feed, rail only, Dutch stations only.
   - Picks the Tue/Wed/Thu and the Saturday with the most trains in the next 4 weeks (fewest engineering works).
2. **Step-free status** ([access.py](stepfree/access.py)): DOVA's NeTEx EPIAP, per platform track, plus hand-kept corrections in [overrides/stations.csv](overrides/stations.csv).
3. **Network** ([network.py](stepfree/network.py)): stops are *platforms*, so changes can depend on which two platforms are involved.
   - Change times:
     - NS's per-station default;
     - shorter where NS explicitly allows a quick connection;
     - never where NS rules a connection out;
     - 2 min on one platform or across an island.
   - A train that continues under a new number counts as one train (you stay seated).
4. **Router** ([raptor.py](stepfree/raptor.py)): RAPTOR (Delling et al. 2012), range version. For every origin it finds every sensible journey leaving between 08:30 and 12:00 with 0, 1 or 2 changes.
5. **Profiles**, applied *during* the search:
   - `any`: no restrictions.
   - `stroller`:
     - board only at step-free platforms at the origin, and leave only from step-free platforms at the destination;
     - change only between two step-free platforms, or on the same platform surface;
     - allow 3 extra minutes per change.
   - Unknown = not step-free.
6. **Train sets**: `all`, or `sprinter` (NS Sprinters plus every regional and cross-border stopping train; no NS Intercity or international trains).
7. **Summaries** ([precompute.py](stepfree/precompute.py)): per destination, the median and fastest duration, departures per hour, and the changes and via stations of the median journey.
8. **Validation** ([validate.py](stepfree/validate.py)): the build only goes live if it passes structural checks, invariants and known answers.

## Output (`data/build/`)

| File | Contents |
|---|---|
| `meta.json` | build time, chosen dates, window, rules, data versions, sources and attribution |
| `stations.json` | per station: code, name, lat/lon, status (`yes`/`partial`/`no`/`unknown`), per-track status, source and date, in-person verification, corrections, lifts (ID, tracks served) |
| `origins/<CODE>.json` | `results[day][profile][train_set][dest]` = list of entries for max 0, 1, 2 changes |

Each entry is `[median_min, fastest_min, departures_per_hour, changes, "VIA|VIA"]`, or `null` when there's no journey with that few changes. Trailing entries that repeat the previous one are dropped, so read level *k* as `list[min(k, len - 1)]`.

Example: `"ASD": [null, [49, 49, 4.0, 1, "UT"]]` means no direct train; with 1 or more changes it's 49 minutes via Utrecht Centraal, 4 departures an hour.

Size: about 87 KB per origin file (10 KB compressed), 34 MB in total.
