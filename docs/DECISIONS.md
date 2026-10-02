# Decisions

One entry per non-obvious decision: what, why, and what was rejected. Newest on top.

---

### 2026-10-02 — Name: Trapvrij, on trapvrij.nl (Daan)
**What:**
- The product is called **Trapvrij**. The domain `trapvrij.nl` is registered at TransIP.
- Error reports go to Daan's address for now. It's set in one place, `web/src/contact.ts`.
- Internal names stay as they are: the Python package `stepfree`, the `STEPFREE_*` settings and the `stepfree-nl` cache folder.

**Why:**
- The name is Dutch, says what the site is about, and doesn't refer to NS or ProRail (principle 5).
- Renaming the internal names would only cause churn.

### 2026-09-30 — More options never make a journey look worse
**What:** Each result shows the best way to travel among the options it allows. With "at most 1 change" you may still go direct; with intercities you may still take only sprinters; a journey that works with a pram works for anyone. So each entry is the best (shortest typical time; then fewer changes, more departures) of its own and those of every variant with fewer options. This happens in the pipeline (`more_options_never_worse`). The validation now checks the typical time, not only the fastest one.
**Why:** Daan found it: from Utrecht C within 30 minutes, 40 stations were reachable direct but only 35 with a change allowed. More options add journeys at in-between times that are often slower, and that raised the median. Utrecht C → Abcoude: 3 direct trains of 20 min, plus more journeys of 31 min via Breukelen. So the median became 31 and Abcoude fell outside 30 minutes. Across all origins, a station dropped out of a slider step about 10,000 times this way, from allowing changes, adding intercities or dropping the pram profile.
**Cost:** a result then describes one way of travelling. Abcoude with "max. 1 overstap" shows the 3 direct trains, not the extra options with a change.
**Rejected:**
- Filtering on the fastest journey: one rare early train would make a place look close.
- Counting waiting time (a door-to-door average) would be monotone too, but the times wouldn't match the NS planner.

### 2026-09-29 — Missing lift data is never shown as "all lifts working"
**What:** The frontend reads an optional `lifts.json`. Without it, the station panel says live lift status is coming and to check before travelling. Phase 3 must never write a placeholder file with an empty outage list.
**Why:** Principle 1: no data must look like no data. An empty list would read as "every lift works".

### 2026-09-29 — Map tiles from OpenFreeMap; the list is the fallback
**What:** The base map uses OpenFreeMap's vector tiles (style *positron* in light mode, *dark* in dark mode), drawn with MapLibre. The credit is on the map and in the footer.
**Why:**
- It's free, with no key, no account and no request limits, and its terms allow use on any site.
- It sets no cookies. I checked the style, tile and font responses.
- No key means nothing for Daan to set up and nothing to leak.

**Risk:** there's no SLA. If the tiles fail, the map area shows a note, and the list (which has the same information) keeps working.
**Rejected:**
- MapTiler, Stadia, Mapbox: they need an account and a key, and their free tiers have caps that could start costing money.
- Hosting our own tiles (Protomaps): more moving parts. It's the plan B if OpenFreeMap becomes unreliable.

### 2026-09-29 — Travel time in five blue bands; every other state by shape
**What:**
- Reachable stations are circles, coloured by typical travel time: up to 30 min, 31–60, 61–90, 91–120, over 2 hours. It's one blue ramp; the quickest band has the most contrast with the base map (dark in light mode, light in dark mode).
- Every other state has its own shape:
  - the origin is a bullseye;
  - "not reachable within your choices" is a hollow ring;
  - "not step-free" is a square with a cross;
  - "unknown" is a diamond with a question mark.
- The legend and the list say everything in words too.

**Why:**
- Travel time is ordered, so one hue going from dark to light reads as more or less at a glance. Five bands are few enough to tell apart.
- Shapes keep "not step-free" and "unknown" readable for colour-blind users and in greyscale (WCAG 1.4.1).
- Both ramps pass the dataviz palette validator against their base map.

**Rejected:**
- A continuous gradient: exact values are hard to read off.
- Traffic-light colours: they imply good and bad, and fail for the most common colour blindness.
- Hiding unreachable stations: then you can't see what's missing, or why.

### 2026-09-29 — The list is the accessible equivalent of the map
**What:** Every station on the map is also in a list. Reachable stations come first, sorted by travel time, with duration, changes, frequency and "via". Below them are folded groups for "not step-free or unknown" and "not reachable". Each item opens the same station panel.
**Why:**
- A map canvas can't be used with a screen reader, and its markers are small.
- The list's buttons are at least 44 px tall. WCAG 2.5.8 accepts the small map markers because an equivalent control meets the size.
- On a phone the list is often the quicker way to browse, and it's the fallback when the tiles fail.

### 2026-09-29 — The visitor's choices live in the URL only
**What:** The origin, the filters and the open station go in the URL hash with Dutch keys, e.g. `#van=HTNC&overstap=2&max=alles`. Values at their default are left out. Nothing goes in cookies or browser storage.
**Why:**
- A view can be shared or bookmarked.
- There's no cookie banner and nothing to clean up.
- Using the hash (not a path or query) keeps the static site simple: every state is the same `index.html`.

**Rejected:** remembering the last origin in local storage. Handy, but not needed for v1.

### 2026-09-29 — Defaults: pram, sprinters, at most 1 change, up to 2 hours, weekday
**What:** A first visit starts with the pram profile, sprinters and stopping trains only, at most one change, up to 2 hours, on a weekday.
**Why:**
- v1 is for pram users, and Daan's rule is to avoid steps inside the train.
- One change and two hours suit a day trip with a small child. The filters widen it.

### 2026-09-29 — The map loads after the page
**What:** MapLibre (about 1 MB of script, 280 KB compressed) is loaded with a dynamic import once the page is up. The page's own script is 9 KB compressed.
**Why:**
- Most users are on a phone, often on a platform. The search and the list answer the question without the map, so they shouldn't wait for it.
- Lighthouse (phone, slow 4G) measures first content at 0.9 s and the largest element at 1.8 s. What's left is MapLibre starting up: about 0.9 s of busy main thread on a throttled CPU.

### 2026-09-29 — The built site goes outside the repo (`STEPFREE_SITE`)
**What:** `npm run build:site` writes the site, plus a copy of the data, to `STEPFREE_SITE` from `.env`, or else to `web/dist`. The dev server reads the data straight from `STEPFREE_BUILD`.
**Why:** The same reason as for the data build: inside Nextcloud, the sync client locks freshly written files. CI uses the default.

### 2026-09-29 — Station search: our own small matcher
**What:** About 130 lines that:
- normalise accents and apostrophes;
- expand shorthand (CS → Centraal, A'dam → Amsterdam, a/d → aan de);
- allow 1 or 2 typos per word, depending on its length;
- rank by match quality, then by how busy the station is.

A short list adds names that share no words with the official one (Den Bosch, Bijlmer, Beukenlaan).
**Why:** 395 names fit in memory. A fuzzy-search library would be bigger than this and wouldn't know Dutch shorthand. Tests cover the typos and abbreviations.
**Rejected:** Fuse.js and similar libraries: generic scoring, no shorthand.

### 2026-09-29 — Working title "Stepfree NL"
**What:** The site says "Stepfree NL (werktitel)" until Daan picks a name.
**Why:** The name is Daan's call and goes with the domain (Phase 3). It must not refer to NS or ProRail (principle 5).

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
