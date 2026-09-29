# Plan

## Phase 0 — Data audit (first; no product code yet)

**Goal:** find out whether open data is good enough to say — reliably and automatically — which stations are step-free. This is the one thing that could kill the project, so settle it before building anything.

### Sources to investigate
Verify current URLs, formats, licences and access requirements yourself; don't trust this list blindly.
- **Timetable:** OVapi GTFS feed for the Netherlands, `http://gtfs.ovapi.nl/gtfs-nl.zip` (CC-BY). Covers all operators, not just NS. It's large (includes all buses) — filter to rail early.
- **Station accessibility and lift status:** ProRail / NS Stations open datasets on accessible routes within stations and live lift availability, published via NDOV Loket. Released as a beta with known completeness gaps — find out where they stand now.
- **NS API** (station information, incl. accessibility-related fields; also useful for checking routes): needs a free subscription key → add to NEEDS_DAAN.
- **OpenStreetMap** via Overpass: `highway=elevator`, `wheelchair=*`, `ramp=*` etc. on stations and platforms — candidate cross-check or fallback.
- **Reference only** (for spot checks; don't build on these without permission): NS station info pages, ProRail's map of step-free stations, treinposities.nl, stationsliftstoringen.nl.

### Questions the audit must answer
1. **Station list.** How many distinct rail stations are in GTFS (parent stations vs platform stops), and which operators? How do you match a station across sources (station code, UIC, name)? Build a master station table.
2. **GTFS accessibility fields.** Is `wheelchair_boarding` populated for rail stops? How often, and does it look plausible?
3. **Step-free status per station.** For each source: coverage (% of stations), granularity (station vs platform), freshness, format, licence, access method (download / API / key).
4. **Platform granularity.** A transfer needs a step-free route between the specific platforms involved. Can we get platform-level data, or must we fall back to "every platform step-free" at station level?
5. **Lift status.** Is there a live feed? How often does it update? Can each lift be tied to a station, ideally a platform? How many lifts are out right now? If feasible, collect snapshots over a few days.
6. **Agreement between sources.** Where two sources cover the same station, how often do they disagree, and on what?
7. **Spot check.** Compare your result against the NS station info page for: Houten, Houten Castellum, Utrecht Centraal, Utrecht Vaartsche Rijn, Geldermalsen, Amersfoort Centraal, Maarssen, Barneveld Noord, Amsterdam Centraal, Zandvoort aan Zee, plus ~10 randomly chosen small stations. Put Houten and Houten Castellum in NEEDS_DAAN for an in-person check.

### Deliverables
- `audit/REPORT.md` — answers to the questions above with numbers, a recommended source strategy, and a suggested verdict.
- `audit/stations.csv` — master station table: ids per source, step-free status per source.
- Reproducible scripts in `audit/` — a fresh checkout can regenerate everything.

### Go / no-go (Daan decides; you recommend)
- **Go** if one source, or a documented combination, gives step-free status for ≥ 90% of stations, can be refreshed automatically, and has a licence that allows display with attribution.
- **Go, narrowed** if coverage is only good in some regions → launch for those regions first.
- **Rethink** otherwise — propose options (e.g. a one-off curated dataset where terms allow, plus user-reported corrections).

**Stop here and report to Daan.**

---

## Phase 1 — Router and precompute
- Rail-only network from GTFS, all operators. No bus/tram/metro legs in v1.
- Two profiles: `any` (baseline) and `stroller`. In `stroller`, the origin, every transfer station and the destination must be step-free. Each route must be possible to ride with a 'sprinter' train, as the stroller is inconvenient with the intercity. The router must **avoid** non-step-free transfer stations during search — not filter results afterwards. Unknown = not step-free.
- Transfer buffer in `stroller` mode: start at +3 minutes on top of the GTFS/default minimum transfer time; log the choice in DECISIONS.md.
- Service days: one representative weekday and one Saturday from the current feed. Departure window 08:30–12:00 (day trips).
- Algorithm: RAPTOR or similar, run for every origin.
- Per origin → destination: typical journey duration (median across departures in the window) and fastest, number of changes, trains per hour, via-stations, and the step-free status of each station involved.
- Output in `data/build/`: one small JSON per origin, plus `stations.json` (name, code, coordinates, step-free status, source, last updated). Keep total size reasonable for a static site.
- Tests: hand-picked pairs with known answers (e.g. Houten Castellum → Utrecht Centraal, 0 changes); ~20 pairs checked against the NS journey planner (via the NS API once the key is available); a test proving a route avoids a transfer station marked not step-free.

## Phase 2 — Map frontend
- Origin search with autocomplete: Dutch station names, tolerant of typos and abbreviations like "Utrecht CS".
- Map of reachable stations coloured by travel time. Unreachable and unknown shown distinctly — never by colour alone.
- Filters: max changes (0 / 1 / 2), max travel time (slider), weekday / Saturday, sprinter / intercity, profile (stroller; wheelchair visible but marked "coming later").
- Station panel: travel time, changes, trains per hour, route via, step-free status with source and date, any current lift outages, links to the station's NS info page and the NS journey planner to double-check.
- Clear disclaimer: indicative information, always check before travelling; wheelchair users should use NS travel assistance.
- Map tiles from a free provider whose terms allow this use; attribution visible.
- Mobile-first, WCAG 2.2 AA, fully keyboard-usable, no cookies or trackers (cookieless analytics at most).
- Reserve `/station/{code}` URLs for the destination pages that come later.

## Phase 3 — Pipeline and launch
- GitHub Actions: nightly rebuild when the GTFS feed has changed. Lift status fetched more often (e.g. hourly) into a small separate `lifts.json`, shown in the frontend as warnings.
- A failing pipeline must never publish broken data: validate outputs, keep the last good build.
- Deploy to Cloudflare Pages. Domain → NEEDS_DAAN.
- About page: what it is, how it works, sources and licences, how to report an error (an email link is fine for v1).

## v1 definition of done
- Live on its own domain; any rail station works as an origin.
- All filters work on a phone.
- Nightly pipeline green for 7 consecutive days.
- Attribution, disclaimer and about page in place.
- Lighthouse accessibility score ≥ 95.

## Not in v1
Wheelchair mode (needs train-type and boarding-gap data), rerouting around live lift outages (v1 only warns), destination "what to do here" pages, user accounts, any backend, bus/tram/metro legs, monetisation.
