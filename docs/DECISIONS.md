# Decisions

One entry per non-obvious decision: what, why, and what was rejected. Newest on top.

---

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
