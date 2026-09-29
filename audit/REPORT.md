# Phase 0 — Data audit report

*Data as of 29 September 2026. Every number here is reproducible with `uv run python run_all.py` (see [README.md](README.md)).*

## Verdict (recommendation — Daan decides)

**Go.** One open source — DOVA's NeTEx EPIAP export on NDOV Loket — gives a step-free status for **395 of the 396** Dutch stations with train service (99.7%). It works per platform track (1,020 tracks), is regenerated **daily**, needs no key, and is **CC0** (no restrictions, though we credit it anyway). After making it more conservative where other sources raise doubts, **392 of 396 stations (99.0%)** have a definite status: 387 step-free, 3 partly (per platform), 2 not step-free, and 4 "unknown" until checked. That's well above the 90% go threshold.

Three caveats, none a blocker:

1. **Every official source comes from one place.** EPIAP, NS's station pages and ProRail's files all come from ProRail's station data, so agreement between them is partly circular. Real ground truth needs in-person checks and an error-report loop (see [NEEDS_DAAN](../docs/NEEDS_DAAN.md)).
2. **Live lift status exists but only as a push stream.** A simple hourly download doesn't work (details under Q5). This is an architecture decision for Phase 3, not a data gap.
3. **"Step-free" in the data means reachable without steps.** It does not guarantee a gentle ramp (about 100 stations had ramps steeper than the wheelchair norm in 2020; fine for a pram) or a short route. It says nothing about the step into the train, which matters for wheelchair mode later.

## Sources investigated

| Source | Where | Licence / terms | Access |
|---|---|---|---|
| **DOVA NeTEx EPIAP** (station accessibility + topology, from the Centraal Haltebestand) | `data.ndovloket.nl/netex/epiap/` | CC0 (NDOV Loket) | daily file, 3.4 MB gz / 88 MB XML, no key |
| **SIRI-FM lift status** (live) | NDOV Loket ZeroMQ `tcp://pubsub.besteffort.ndovloket.nl:7666`, envelope `/DOVA/ServiceDelivery` | CC0; fair use: 1 connection | push stream, no key |
| OVapi GTFS (timetable, all operators) | `gtfs.ovapi.nl/nl/gtfs-nl.zip` | free use, no SLA, don't claim to represent the operators; identify yourself in the User-Agent, use conditional GET + gzip. **Not CC-BY as the plan assumed**, but we'll credit OVapi / Stichting OpenGeo anyway. | daily, 245 MB |
| NS IFF timetable (station attributes) | `data.ndovloket.nl/ns/ns-latest.zip` | CC0 | daily |
| ProRail step-free map input (2019–2020) | `data.ndovloket.nl/prorail/` | CC0 | one-off xlsx |
| ProRail boarding-height status per track (Q2 2026) | same | CC0 | quarterly-ish xlsx |
| ProRail asset register: lifts, ramps, platforms (June 2026) | same | CC0 | twice-yearly CSV |
| OpenStreetMap | Overpass API | ODbL (attribution; share-alike if we publish derived data) | one query, cached 7 days |
| NS API | apiportal.ns.nl | NS terms | needs a key; **not tested** (in NEEDS_DAAN, not needed for accessibility) |
| NS station pages | ns.nl/stationsinformatie | reference only | spot checks by hand |

Not usable: ProRail's 2022 step-free map is a PDF image, so it isn't machine-readable.

## Q1 — Station list and matching

- The GTFS feed has **549 rail parent stations** (1,327 platform stops). **396 are in the Netherlands** (per the NS station country code); 153 are abroad (106 DE, 29 BE, …). A further 10 platform stops without a parent station belong to the Miljoenenlijn heritage railway (ZLSM, Zuid-Limburg). They're left out of the counts and flagged as heritage.
- Operators at the 396 Dutch stations (a station can have several): NS 248, Arriva 102 (+ RRReis 37, Blauwnet 36), NS International 25, R-net 19, European Sleeper 9, GoVolta 8, Eurobahn 3, DB 3, VIAS 2, NMBS 1.
- **Matching key: the NS station code** (e.g. `HTN`). It appears in every source: GTFS `zone_id` (`IFF:htn`), EPIAP `PrivateCode` (`NL:S:htn`), IFF, ProRail's "Afkorting", ProRail asset IDs (`HTN-LIF-001`), and OSM `railway:ref`. EPIAP also gives the **UIC code** (StopPlace id, e.g. `8400340`).
- Match rates for the 396 stations: EPIAP 396 (100%), ProRail 2020 394 (the other two opened or were renamed later: Delft Campus, Utrecht Maliebaan), ProRail boarding 395 (by name), OSM 390.
- EPIAP has 412 rail stop places: the 396, plus 6 foreign border stations, 8 heritage stops and 2 event-only stations not served in this feed (Eindhoven Stadion, Heerenveen IJsstadion).
- Master table: [stations.csv](stations.csv), one row per station with IDs and every source's status.

## Q2 — GTFS `wheelchair_boarding`

- Parent stations: always `0` ("no information").
- Platform stops: `1` or empty. 317 stations have `1` on every platform, 77 have none, 2 are mixed.
- **It's a copy of NS's "TGST" station attribute** from the IFF timetable. They agree on all 396 stations.
- **It doesn't mean step-free.** TGST is missing at Amsterdam, Rotterdam, Den Haag, Amersfoort, Arnhem and Eindhoven Centraal, Zwolle, Breda…, all of which have lifts to every platform. It tracks **level boarding** instead: 253 of 319 TGST stations have every track at the new platform height, against 4 of 77 non-TGST stations.
- **Conclusion:** not usable for the pram profile. Keep it in mind for wheelchair mode.

## Q3 — Step-free status per source (396 stations)

| Source | yes | partly | no | unknown | Granularity | Freshness |
|---|---|---|---|---|---|---|
| **EPIAP** | **390** | 3 | 2 | 1 | per track (1,008 true, 5 false, 7 unknown of 1,020) | daily |
| ProRail 2020 | 383 | – | 11 | 2 | station | 2019–2020 |
| OSM `wheelchair` | 245 | 16 ("limited") | 7 | 128 untagged | station | crowd-sourced |
| NS TGST / GTFS | 319 | – | 77 | – | station | daily, but a different meaning (see Q2) |

The ProRail 2020 workbook has a trap. In its newer sheet (*Uitrollijst (ex AVG)*), the first column (*Station*) was sorted separately from the rest. Only *StationCorrectie* and *Afkorting* line up with the status, date and notes. Two rows also contradict themselves (Vught, Gorinchem). The parser uses the aligned columns and falls back to the older sheet.

## Q4 — Platform granularity

- **Yes, per platform track.** Each EPIAP quay (track side, e.g. Utrecht Centraal 18) has `StepFreeAccess`, `WheelchairAccess` and `LevelAccessIntoVehicle`. Island platforms and sectors (4a/4b) are separate quays with parent links.
- **GTFS platforms map onto them:** 1,061 of 1,075 platform stops (98.7%) match an EPIAP quay by platform code. Most of the other 14 are rail-replacement bus stops that GTFS files under train routes. Phase 1 must handle those.
- **The station topology is not complete enough to route with.** EPIAP also models entrances, halls, lifts, ramps and walking links. Following those links, all tracks connect to a street entrance at **295 of 396** stations (307 if halls count as reachable). The model is built around lifts. Ground-level access and hall-to-street links are often missing (40 stations have no links at all).
- **Recommendation for Phase 1:** a transfer is step-free when both the arrival and departure tracks are `StepFreeAccess=true`. Each such track is reachable from the street, so worst case you can change via the street. Fall back to station level when a platform can't be matched. Keep the +3 min buffer.

## Q5 — Lift status

- **A live feed exists:** SIRI-FM (Dutch profile TMI9 v9.0), CC0, on the NDOV Loket ZeroMQ stream. It connected without a key.
- **Lift IDs are EPIAP IDs** (`NL:CHB:LiftEquipment:8400340_001`), so each lift ties to its station directly.
  - 446 lifts at rail stations; 442 marked as monitored.
  - **336 are linked to specific tracks** (a lift on an island platform serves both tracks). The rest mostly serve halls, squares, bus platforms or bridges; a few platform lifts only name their track in the description (e.g. `ZP-LIF-002 Spoor 2/3`).
  - Cross-check: EPIAP and ProRail's June 2026 asset register share **421 lift codes**. The differences are explainable: goods and parking lifts, lifts ProRail doesn't manage, and recent rebuilds.
- **Update behaviour (from the spec):**
  - a message on every status change;
  - the **full state of all lifts once a day**;
  - a heartbeat every 60 minutes;
  - long outages (a week or more) carry start and end dates.
- **How many lifts are out right now:** not yet known, because that needs the daily full-state message. A logger (`lift_listener.py`) is recording the feed for 72 hours from 29 Sep 21:12 CEST. In the first minutes it already caught `ASD-LIF-013` (Amsterdam Centraal, east tunnel, tracks 10/11) **out since 19 June 2024**. Those tracks stay reachable through the west-tunnel lift (`ASD-LIF-025`), which shows why the lift-to-track link matters.
- **Architecture consequence (Phase 3):** an hourly GitHub Actions job can't just download the current state. Options, cheapest first:
  - (a) catch the daily full-state message plus the long-outage dates with a short scheduled listening window;
  - (b) a small always-on listener;
  - (c) ask NDOV Loket (Reisinformatiegroep) whether a pull or snapshot endpoint exists.

  To decide once the 72-hour log shows when the daily snapshot arrives.

## Q6 — Agreement between sources

- **EPIAP vs ProRail 2020** (394 stations): agree on 381 (96.7%). The 13 differences:
  - **6 upgraded since 2019:** the 2020 list says "no", EPIAP says "yes", and ProRail's 2026 asset register now lists lifts or ramps (Alkmaar Noord, Arnhem Velperpoort, Den Haag HS, Dordrecht Zuid, Driehuis, Gorinchem).
  - **2 unexplained:** 2020 "no", EPIAP "yes", but no lift or ramp in either EPIAP or the register (**Eindhoven Strijp-S, Rotterdam Stadion**). Kept as *unknown* until checked.
  - **Vught:** EPIAP says "no". It's a temporary station during the railway rebuild; the 2020 row contradicts itself.
  - **Blerick:** EPIAP says track 3 isn't step-free while track 2 on the same island platform is. A data anomaly; track 3 is kept as "no".
  - **Den Haag Centraal, Groningen:** "partly", because 2 tracks each are *unknown* in EPIAP (new or rebuilt tracks).
  - **Wolfheze:** unknown in EPIAP, "no" in 2020. Stays unknown.
- **EPIAP vs OSM** (268 tagged stations): agree on 245 (91.4%).
  - Most differences are OSM `limited` where EPIAP says yes (14), which usually means a steep ramp or a boarding gap.
  - Of the 6 OSM "no"s, four have lifts to all platforms in the register (Alkmaar, Bloemendaal, Gouda, Nijmegen Dukenburg), so OSM is likely outdated.
  - **Diemen Zuid** (its lift is marked as a *project* in the register) and **Eindhoven Strijp-S** stay doubtful.
- `stations.csv` has a `recommended_status` column: EPIAP, but set to *unknown* where another source says "no" **and** there is no lift or ramp, or the lift is still a project. A `review_reason` column explains each of the 15 flagged stations.

## Q7 — Spot check against NS station pages

Checked by hand, slowly, reading only: Houten, Houten Castellum, Utrecht Centraal, Utrecht Vaartsche Rijn, Geldermalsen, Amersfoort Centraal, Maarssen, Barneveld Noord, Amsterdam Centraal and Zandvoort aan Zee. Plus 10 random small stations (seed 20260929): Castricum, Oudenbosch, Warffum, Bedum, Maastricht Noord, Dalfsen, Meerssen, Hoensbroek, Heerlen Woonboulevard, Hoogeveen.

- **20 / 20 match.** Each NS page lists the same lifts as EPIAP (e.g. Utrecht Centraal 18, Amsterdam Centraal 15, Geldermalsen 3 with the same track descriptions), and EPIAP calls all 20 step-free.
- **This is not independent confirmation.** NS pages use the same data (their facility links carry the EPIAP ID, e.g. `?facility=nl-chb-liftequipment-8400340-001`). They also never state a step-free verdict: Arnhem Presikhaaf, which has no lift, shows no warning at all.
- **Ground truth therefore needs eyes on site:** Houten and Houten Castellum are in NEEDS_DAAN, plus a desk check of the 3 doubtful stations.

## Recommended source strategy

1. **Step-free status: EPIAP, per track.** A station is "step-free" only if every track is; otherwise decide per platform. Unknown means not step-free.
2. **A hand-kept overrides file** (`station`, `track`, `status`, `reason`, `source`, `date`) for anomalies and in-person findings. It is applied after EPIAP and always wins when it is more conservative.
3. **Daily refresh** in the nightly pipeline. Keep dated snapshots, and flag any station whose status changes, as a warning to review rather than an automatic publish of "yes".
4. **Lift outages from SIRI-FM** as warnings on the station panel. The collection design is decided in Phase 3.
5. **Don't use** GTFS `wheelchair_boarding` or NS TGST for step-free status. Keep them, plus EPIAP `LevelAccessIntoVehicle` and ProRail's track-height data, for wheelchair mode.
6. **OSM only as a desk cross-check.** Publish nothing derived from it (avoids the ODbL share-alike obligation).
7. **Credit on the site:** DOVA / ProRail via NDOV Loket (EPIAP, SIRI-FM), OVapi / Stichting OpenGeo (GTFS), NS (IFF).
8. **A "report an error" link** from day one: the data has one upstream, so users are our second opinion.

## Reproduce

See [README.md](README.md). Downloads are cached in `data/raw/` (git-ignored), so the first run takes a few minutes (245 MB GTFS) and later runs take about 15 seconds.
