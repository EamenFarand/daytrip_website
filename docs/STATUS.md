# Status

*Last updated: 2026-09-29 (end of session 1)*

## Where we are
**Phase 1 (router and precompute) is done. Waiting for Daan's review and go for Phase 2** ([NEEDS_DAAN](NEEDS_DAAN.md) item 1).
The only open Phase 1 item is comparing ~20 routes with the NS journey planner. The code is ready, but it's waiting for the NS API key (NEEDS_DAAN item 4).

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
