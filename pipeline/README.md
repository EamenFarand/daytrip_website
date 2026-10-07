# Pipeline: router and precompute (Phase 1)

Builds everything the site loads. No AI at runtime, just this code.

```bash
cd pipeline
uv sync
uv run python -m stepfree.build          # ~2.5 min on 4 cores; downloads are cached
uv run pytest                            # 73 tests; the NS comparison skips until NS_API_KEY is set
uv run python -m stepfree.ns_check       # our journeys vs the NS journey planner (needs NS_API_KEY)
```

Options: `--today 2026-09-29` (reproducible day choice), `--only HTNC UT` (quick run for a few origins), `--workers 4`.

Locally, downloads and output live outside the repo, set in `.env` (`STEPFREE_CACHE`, `STEPFREE_BUILD`), so Nextcloud doesn't sync them. `STEPFREE_TRAINS` (a file) replaces the download of the train record (see Train sets), for local tries. Without those settings (as in CI) they go to `data/raw/` and `data/build/`. Both are git-ignored.

## What it does

1. **Timetable** ([gtfs.py](stepfree/gtfs.py)): the OVapi GTFS feed, rail only, Dutch stations only.
   - Picks the Tue/Wed/Thu and the Saturday that serve the most regular stations, then have the most stops, in the next 8 weeks and within the yearly timetable that's running (fewest engineering works; DECISIONS 2026-10-07).
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
6. **Train sets** ([trains.py](stepfree/trains.py)): `all`, or `sprinter`, which the site calls "Zonder trapjes" (trains without steps).
   - First NS's own mark per train unit (accessible or not). The lift listener records it from NS's journey messages; the build downloads it from `https://trapvrij.nl/api/trains`, or uses the last copy.
   - Per train number and day type, over the last four weeks of the same yearly timetable:
     - seen once with a unit that isn't accessible: out;
     - seen at least 3 times, always accessible: in, intercities too (usually the ICNG).
   - Otherwise, and without a record younger than two weeks, the category decides: NS Sprinters and every regional and cross-border stopping train; no NS Intercity or international trains.
7. **Summaries** ([precompute.py](stepfree/precompute.py)): per destination, the median and fastest duration, departures per hour, and the changes and via stations of the median journey.
8. **More options never look worse** (`more_options_never_worse`). Each entry becomes the best (shortest median) of its own and those of the variants with fewer options: fewer changes, sprinters only, or the pram profile. Without this step, allowing a change could make a destination's typical time *longer*. For example, Utrecht C → Abcoude has 3 direct trains of 20 min, but more journeys of 31 min with a change. Abcoude then dropped out of a 30-minute filter when you allowed a change.
9. **Validation** ([validate.py](stepfree/validate.py)). The build only goes live if it passes two sets of checks:
   - on the raw router output: more options are never slower;
   - on the files: structure, never a longer typical time with more options, and known answers.

## Output (`data/build/`)

| File | Contents |
|---|---|
| `meta.json` | build time, chosen dates, window, rules, data versions, sources and attribution |
| `stations.json` | per station: code, name, lat/lon, status (`yes`/`partial`/`no`/`unknown`), per-track status, source and date, in-person verification, corrections, lifts (ID, tracks served) |
| `origins/<CODE>.json` | `results[day][profile][train_set][dest]` = list of entries for max 0, 1, 2 changes |

Each entry is `[median_min, fastest_min, departures_per_hour, changes, "VIA|VIA", "TRACKS", 1?]`, or `null` when there's no journey with that few changes. Trailing entries that repeat the previous one are dropped, so read level *k* as `list[min(k, len - 1)]`.
- `VIA` is empty for a direct journey.
- `TRACKS` are the typical journey's tracks: departure, then arrival and departure at each change, then arrival. `?` means the timetable doesn't say. The site uses them to warn only about lifts on those tracks.
- A final `1`: the typical journey takes an intercity that counts as without steps because NS marks it accessible. The site then says NS sometimes runs another train.

Example: `"ASD": [null, [49, 49, 4.0, 1, "UT", "1|20|5|5a"]]` means no direct train. With 1 or more changes it's 49 minutes via Utrecht Centraal (in on track 20, out from 5), arriving on track 5a, with 4 departures an hour.

`stations.json` gives each station a `slug` for its page (`/station/<slug>/`), unique and checked by the build. `meta.json` has `trains`: when the train record was made and how many trains got a verdict. It also has `inputs`: hashes of the sources, the corrections, the pipeline code and the train verdicts. The nightly job compares them with the live build to skip a build when nothing changed (`stepfree.inputs`).

Size: about 110 KB per origin file (about 20 KB compressed), 44 MB in total.
