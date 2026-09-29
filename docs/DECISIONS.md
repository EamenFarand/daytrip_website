# Decisions

One entry per non-obvious decision: what, why, and what was rejected. Newest on top.

---

### 2026-09-29 — "Sprinter" train set = NS Sprinters + all regional stopping trains (Daan: option A)
**What:** The sprinter set is:
- NS: only trips labelled *Sprinter*;
- every trip run by regional or cross-border operators (Arriva, Blauwnet, RRReis, Qbuzz and R-net, Keolis; DB, Eurobahn, VIAS, NMBS stopping trains), whatever their label.

It excludes NS Intercity, Intercity direct and all NS International trains. Both train sets are precomputed, and Phase 2 gets a sprinter/intercity filter.
**Why:** Daan: *any train taken must avoid steps inside the train*. Sprinters and regional trains are low-floor; intercities have steps.
**Rejected:**
- Option B (regional *Stoptrein* only).
- Rolling-stock-level rules: GTFS doesn't say which train type runs, e.g. step-free single-deck ICNG versus double-deck VIRM.

### 2026-09-29 — Trains we never route on
**What:** Excluded from every train set:
- NS's *Drempelvrije bus* (a bus filed as rail);
- the Miljoenenlijn heritage line;
- Eurostar, European Sleeper, GoVolta and Nightjet (own tickets or compulsory reservation).

ICE, EuroCity and Intercity direct stay in the "all trains" set; they're usable with a domestic ticket, sometimes with a supplement.
**Why:** A day-trip tool should only suggest trains you can board with a normal ticket.

### 2026-09-29 — Router: our own platform-level RAPTOR, not a library
**What:** About 300 lines of Python implementing range RAPTOR (Delling et al. 2012). Stops are platforms. Station accessibility is enforced during the search (where you may board, leave and change), never filtered afterwards.
**Why:**
- The stroller rules need platform-level checks inside the search.
- Plain Python is fast enough: about 0.3 s per origin and variant, 2.5 min for the full build on 4 cores.
**Rejected:**
- r5py / OpenTripPlanner: a heavy Java runtime, and custom accessibility rules are awkward there.
- Trip-based routing: more precise with trip-specific transfer rules, but more complex. Revisit if the NS comparison shows problems.

### 2026-09-29 — How long a change takes
**What:**
- Default: NS's per-station transfer time from the IFF timetable (2, 4 or 5 min; 0 is read as 2).
- Same platform, or across an island platform: 2 min.
- A platform pair gets the shortest connection NS explicitly lists as possible, if shorter than the default (GTFS `transfers.txt` type 0, all 2–4 min).
- Connections NS lists as impossible (type 3) are never used.
- **Stroller: +3 min on every change** (plan default).
**Why:**
- Without NS's short connections we'd miss the designed cross-platform changes at Utrecht, Amersfoort and elsewhere.
- Without the ruled-out ones we'd suggest connections NS says don't work.
**Known limitation:** the router keeps one best arrival per platform, so a ruled-out connection is only checked against the train on that best arrival. This errs on the side of fewer options.

### 2026-09-29 — Changing on one platform surface is step-free, even at a station without lifts
**What:** In the stroller profile, a change is allowed if both platforms are step-free, **or** both tracks are on the same platform surface (same track, sectors of it, or two sides of one island platform, per EPIAP).
**Why:** Walking across a platform involves no stairs. The station's street access doesn't matter for that change.

### 2026-09-29 — Trains that continue under a new number are one train
**What:** Merge trip A into trip B when:
- A ends at a platform and B starts there within 5 min;
- NS lists the connection as possible;
- B doesn't go back the way A came.

It's not a change, needs no buffer, and has no step-free requirement.
**Why:** On a weekday this affects 46 Arriva trains (through trains at Groningen and Venlo). Otherwise they would count as a change, and the +3 min stroller buffer would break them.

### 2026-09-29 — Journeys: first train leaves the origin between 08:30 and 12:00; compare only within that window
**What:**
- For each departure in the window, find the earliest arrival with at most 0, 1 or 2 changes.
- Keep only sensible journeys: drop any that leaves earlier *and* arrives no earlier than another.
- Median = lower median of those journeys (always a real journey); departures per hour = count ÷ 3.5.
**Why:** At first I also searched 90 min past 12:00 so late slow journeys would be compared fairly. But then a faster 12:05 journey hid every in-window journey, and some destinations looked unreachable. Validation caught this.

### 2026-09-29 — Representative days: the fullest Tue/Wed/Thu and Saturday in the next 4 weeks
**What:** Count rail trips per date in the feed. Pick the Tue/Wed/Thu with the most (Wed 21 Oct in the first build) and likewise for Saturday (24 Oct). Ties go to the earliest.
**Why:** Engineering works show up as missing trains, so the fullest day is the most normal one. Mondays and Fridays are skipped because they sometimes differ.

### 2026-09-29 — Timetable platform unknown to EPIAP
**What:** If a timetable platform code doesn't match EPIAP, treat it as step-free only if:
- every EPIAP track at that station is step-free, **and**
- the timetable uses no more (known) platforms there than EPIAP has.

Otherwise it's unknown.
**Why:**
- Glanerbrug and Enschede De Eschmarke have one track, but some trains carry no platform code.
- Santpoort Noord (1/3 vs 1/2) and Delft Campus (1/2 vs 2/4) are numbered differently in the two sources.

The count check catches a genuinely extra platform (e.g. Tilburg track 4 stays unknown).

### 2026-09-29 — Corrections file for step-free status
**What:** `pipeline/overrides/stations.csv`, one row per station or track, with reason, source and date. It's applied after EPIAP; a typo fails the build.

It currently holds:
- Houten and Houten Castellum: confirmed in person by Daan;
- Eindhoven Strijp-S, Rotterdam Stadion, Diemen Zuid: unknown (from the audit);
- Blerick track 2: unknown (EPIAP says its island twin, track 3, isn't step-free).

**Why:** We need a place for in-person findings and data anomalies that survives the daily refresh.

### 2026-09-29 — Build output is not committed; build → validate → swap
**What:** `data/build/` is git-ignored. The build writes to `build.tmp`, validates, then replaces `build`. Locally, both cache and output live outside the repo (`.env`: `STEPFREE_CACHE`, `STEPFREE_BUILD`).
**Why:**
- The output is 34 MB and changes nightly, which would bloat git.
- CI will build and deploy it directly (Phase 3).
- Inside Nextcloud, the sync client locked freshly written files and broke the build (also 1.5 GB of downloads was syncing).
**Rejected:** committing the build, which is what the original layout suggested.

### 2026-09-29 — Step-free status comes from DOVA NeTEx EPIAP, per track
**What:** Use the daily EPIAP export on NDOV Loket (`netex/epiap/`, CC0) as the primary source. A station is step-free only if every track is `StepFreeAccess=true`; otherwise decide per platform.
**Why:** It covers 395/396 stations and 1,020 tracks, refreshes daily, needs no key, and its IDs link to the live lift feed.
**Rejected:**
- GTFS `wheelchair_boarding` / NS IFF `TGST`: the same flag, and it means level boarding, not step-free access. Amsterdam Centraal is "no".
- ProRail's 2020 list: six years old.
- OSM: a third of stations are untagged, the meanings vary, and ODbL share-alike would apply if we published it.

### 2026-09-29 — Conservative override when sources conflict
**What:** `recommended_status` = EPIAP, except *unknown* when another source says "no" **and** neither EPIAP nor ProRail's asset register has a lift or ramp there (or the lift is still a "project"). Today that affects 3 stations.
**Why:** Principle 1: a wrong "yes" strands someone. Where the register shows new lifts, the "no" is explained by an upgrade, so we keep EPIAP's "yes".
**Rejected:**
- Downgrading every conflict (13 stations). Most are upgrades since 2019, and OSM's "no" is often about boarding.
- Trusting EPIAP blindly.

### 2026-09-29 — NS station code is the join key
**What:** Join all sources on the NS station code (upper case). Keep UIC from EPIAP as a secondary ID.
**Why:** It is present in GTFS (`zone_id`), EPIAP, IFF, ProRail files, lift IDs and OSM, and matched 100% between GTFS and EPIAP.

### 2026-09-29 — Station universe: GTFS rail stations in NL, heritage excluded
**What:** 396 stations: GTFS parent stations served by a rail route, with NS country code NL. The Miljoenenlijn (ZLSM heritage line) is left out.
**Why:** It is a museum line with no parent stations in GTFS and no accessibility data in EPIAP.

### 2026-09-29 — ProRail 2020 workbook: newer sheet, aligned columns only
**What:** Read *Uitrollijst (ex AVG)* using *StationCorrectie* / *Afkorting* (not *Station*), falling back to *Uitrollijst* for the three stations missing there.
**Why:** In the newer sheet, the *Station* column was sorted separately from the rest. The notes (e.g. Gorinchem "only via service crossing") prove which columns belong together.

### 2026-09-29 — NS website used only for a 20-page manual spot check
**What:** Read NS station pages by hand in the browser (robots.txt allows them; non-essential cookies declined). Record only a yes/no consistency result, never store or reuse content.
**Why:** The plan names them as reference only. They also turned out to be built on the same EPIAP data, so they can't be an independent source anyway.

### 2026-09-29 — OVapi GTFS licence is "free use, no SLA", not CC-BY
**What:** The feed README states free use with conditions: identify yourself in the User-Agent, use conditional requests and gzip, and don't claim to represent the operators. It does not mention CC-BY. We still credit OVapi / Stichting OpenGeo.
**Why:** PLAN.md assumed CC-BY. This records the actual terms.

### 2026-09-29 — Audit is its own uv project, pinned to Python 3.12
**What:** `audit/` has its own `pyproject.toml` / `uv.lock`, pinned to Python 3.12 (the machine default is 3.14).
**Why:** The stack says Python 3.12. Keeping the throwaway audit separate from the future `pipeline/` keeps its dependencies (pyzmq, openpyxl) out of production.
