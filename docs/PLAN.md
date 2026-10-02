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
*Expanded on 2026-10-01 after Daan's Phase 2 review: live lift status, station pages and housekeeping were added.*

- GitHub Actions: nightly rebuild when the GTFS feed has changed. Run the pipeline and web tests in CI.
- A failing pipeline must never publish broken data: validate outputs, keep the last good build.
- Deploy to Cloudflare Pages. Domain → NEEDS_DAAN.
- About page: what it is, how it works, sources and licences, how to report an error (an email link is fine for v1).

### Live lift status
- **Where the listener runs: on Daan's home server.** Decided on 2026-10-02, option (b), after the lift-log analysis in `audit/REPORT.md` Q5. See DECISIONS.md.
  - The SIRI-FM feed is a push stream: changes as they happen, plus a full snapshot every night at 04:02.
  - A listener in a Docker container on the home server (Linux, always on) holds our one connection to the feed. It keeps the state of every lift, resets it with each 04:02 full state, and applies changes as they arrive.
  - When something changes, at most every 2 minutes, it writes `lifts.json` to Cloudflare Workers KV. It uses a second Cloudflare key that can only edit KV, and makes outgoing connections only.
  - The site reads `lifts.json` through a tiny, read-only Cloudflare Pages Function, cached for about a minute. That's our only server-side code.
  - The code lives in the repo, in `lifts/`: the listener, a Dockerfile, a compose file and install steps. Daan runs it on the server.
  - Also ask NDOV Loket (option c) for a pull endpoint and about 2 Oct, when the change stream stayed silent for more than 19 hours.
- **Warn on the whole journey, not only the clicked station.** For a journey, check lifts at the origin, every transfer station and the destination. Where possible, only check the lifts serving the platforms used (EPIAP links lifts to tracks). If the build doesn't store platforms per journey, warn per station for now.
  - Show the warning in the station panel, next to the station in "Overstappen in", and on the list entry.
  - A transfer station must never read as plain "drempelvrij" while a lift that may serve the journey is out of order.
- **Stale data looks like no data.** `lifts.json` records when its last full snapshot arrived. If that is more than about 26 hours ago, the site says lift status is unknown instead of showing no warnings. It also records when the last status message arrived. Two lifts normally resend every 5 minutes, so after about 30 minutes without any, the site says it shows the status of the last full snapshot. Validate `lifts.json` before publishing it, like the build. Never publish an empty or placeholder file (see DECISIONS, 2026-09-29).

### Station pages (findability)
- **Why:** the site is one page with its state after the `#`, so search engines see a single page. Most visitors will arrive from searches like "kinderwagen trein Houten", and so will any later revenue.
- At build time, generate a static, pre-rendered HTML page per station under `/station/…`. Choose between the code and a readable slug (e.g. `/station/houten-castellum`), and log the choice. Each page has:
  - its own title and meta description, e.g. "Met de kinderwagen vanaf Houten Castellum";
  - the station's step-free status and lifts;
  - a short summary of the stations reachable from it with a pram, within 30 and 60 minutes;
  - the interactive map loading on top, with that station as the origin.
- The pages make sense without JavaScript. Keep Lighthouse accessibility and SEO at ≥ 95 on a sample of them.
- Add `sitemap.xml` and canonical URLs. robots.txt allows the pages and keeps `/data/` disallowed.
- All text is generated from the data by plain code, with no AI at runtime (principle 2). Editorial "what to do here" content stays out of v1.

### Housekeeping
- NEEDS_DAAN item 8 only says to exclude `.git` from Nextcloud. About 500 MB of `node_modules` and `.venv` folders also sit inside the project and sync. Correct the item: exclude `node_modules` and `.venv` too.

## v1 definition of done
- Live on its own domain; any rail station works as an origin.
- All filters work on a phone.
- Nightly pipeline green for 7 consecutive days.
- Attribution, disclaimer and about page in place.
- Lighthouse accessibility score ≥ 95.
- Every station has its own pre-rendered page, listed in the sitemap.
- Lift warnings cover the origin, transfer stations and destination, and stale lift data shows as unknown.

## Not in v1
Wheelchair mode (needs train-type and boarding-gap data), rerouting around live lift outages (v1 only warns), editorial "what to do here" content on station pages, user accounts, any backend (apart from the home-server lift listener and the small function that serves its data), bus/tram/metro legs, monetisation.
