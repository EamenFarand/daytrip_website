# Status

*Last updated: 2026-09-29 (end of session 1)*

## Where we are
**Phase 2 (map frontend) is mostly built and working, but not yet reviewed or documented.** Session 1 ended at the usage limit mid-phase.
Phase 1 is done; Daan gave the go for Phase 2 and confirmed Den Haag C and Groningen are fully step-free (now in the corrections file).

### Phase 2: done so far (`web/`)
- Vite + TypeScript + MapLibre 6. Run: `npm --prefix web run dev` (or the "web" entry in `.claude/launch.json`).
  Data is served from `STEPFREE_BUILD` (`.env`). The built site goes to `STEPFREE_SITE`: `npm --prefix web run build:site`.
- Station search that tolerates typos and abbreviations ("Utrecht CS", "A'dam", "Den Bosch", station codes).
- Filters: profile (wheelchair shown as "komt later"), trains, day, max changes, max time. Folded on phones.
- Map (OpenFreeMap tiles): stations coloured by travel time; other states shown by shape; legend.
- List view as the accessible equivalent of the map, sorted by time.
- Station panel: status with source and date, journey, lifts, NS links. `/station/<code>` works.
- State is kept in the URL hash (shareable); no cookies or storage.
- The map is lazy-loaded: the page is 22 KB of JS, the map about 280 KB compressed, loaded after.
- Checks passed:
  - axe-core: 0 violations in light, dark and phone layouts;
  - `npx vitest run`: 34 tests;
  - the production build was tested in `vite preview`.
- Spot check against the NS planner website (reference only) for 4 routes: all match.

### Phase 2: left to do
1. `docs/DECISIONS.md` entries for:
   - OpenFreeMap tiles (no SLA; the list works without the map);
   - blue ordinal ramp in 5 bands (validated);
   - shapes for the other states;
   - URL-only state;
   - defaults: pram + sprinters + 1 change + 2 h;
   - lazy map;
   - `STEPFREE_SITE`;
   - "werktitel" Stepfree NL.
2. `web/README.md`; commit anything not yet committed.
3. NEEDS_DAAN:
   - product name + domain (Phase 3);
   - a contact email for error reports (the about page says "komt eraan");
   - review of the site (screenshots or run it locally).
4. Lighthouse accessibility score (the v1 goal is ≥ 95), e.g. `npx lighthouse` against the preview.
5. Then stop and summarise Phase 2 for Daan.

## Done
- **Phase 0**: data audit, verdict Go. See `audit/REPORT.md`.
- **Phase 1**, in `pipeline/` (see `pipeline/README.md`):
  - `uv run python -m stepfree.build` builds `meta.json`, `stations.json` and 395 `origins/<CODE>.json`. It takes about 2.5 min on 4 cores; output is 34 MB (about 10 KB compressed per origin).
  - Router: platform-level range RAPTOR, with the stroller profile enforced during the search, both train sets (all / sprinter), weekday Wed 21 Oct and Saturday 24 Oct, 08:30–12:00, 0/1/2 changes.
  - The build → validate → swap step blocks broken output: structural checks, invariants (pram never faster, sprinter never faster, more changes never slower) and known answers.
  - Tests: `uv run pytest`, 46 passing and 1 skipped (NS API). They include hand-made networks proving the stroller route avoids a transfer station without step-free access, and the same proof on real data (Houten Castellum → Amersfoort with Utrecht C blocked).
  - Corrections file `pipeline/overrides/stations.csv`: Houten and Houten Castellum verified by Daan in person, plus the audit's conservative corrections.
- Housekeeping: the download cache and build output moved outside Nextcloud via `.env` (`STEPFREE_CACHE`, `STEPFREE_BUILD`). `data/build/` is git-ignored; CI will deploy it in Phase 3.

## In progress
- `audit/lift_listener.py` is logging the live lift feed to `data/raw/lifts/` until about 2 Oct 21:12.
  - Next session: analyse it. When does the daily full snapshot arrive, and how many lifts are out? Add the answers to `audit/REPORT.md` Q5.
  - Then move `data/raw/lifts` to the cache folder too.

## Next step
1. When the NS API key arrives: `cd pipeline && uv run python -m stepfree.ns_check`. Investigate any route off by more than 5 min.
2. When Daan says go: **Phase 2**, the map frontend in `web/` (Vite + TypeScript + MapLibre).
   - It reads `stations.json` and `origins/<CODE>.json`; the format is in `pipeline/README.md`.
   - The sprinter/intercity filter maps to `train_set`, the profile to `stroller`/`any`, the day to `weekday`/`saturday`.
   - "Unknown" and "not step-free" stations must look different from "no journey", and never by colour alone.
3. Waiting on Daan (see NEEDS_DAAN):
   - Den Haag C 11–12 / Groningen 2–3 check;
   - NS API key;
   - Nextcloud `.git` ignore;
   - optional DOVA report.

## How to resume
- Read `CLAUDE.md`, this file, `docs/PLAN.md`, `docs/DECISIONS.md` (newest first), then `pipeline/README.md`.
- `cd pipeline && uv sync && uv run pytest && uv run python -m stepfree.build`. Downloads are cached; paths come from `.env`.
- If `.env` is missing (fresh checkout), everything goes to `data/raw` and `data/build`, which is fine outside Nextcloud.
