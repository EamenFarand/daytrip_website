# Status

*Last updated: 2026-09-29 (end of session 1)*

## Where we are
**Phase 0 (data audit) is done. Waiting for Daan's go/no-go** ([NEEDS_DAAN](NEEDS_DAAN.md) item 1).
Recommendation: **Go**. See the verdict in [audit/REPORT.md](../audit/REPORT.md).

## Done
- Git repo set up and pushed to https://github.com/EamenFarand/daytrip_website (`main`).
- Phase 0 audit in `audit/`:
  - `REPORT.md`: answers to Q1–Q7, source strategy and verdict.
  - `stations.csv`: 396 Dutch rail stations with IDs and each source's status.
  - Reproducible scripts: `uv run python run_all.py`. Tests: `uv run pytest` (4 passing).
- Key findings:
  - DOVA NeTEx EPIAP (daily, CC0) gives per-track step-free status for 395/396 stations.
  - GTFS `wheelchair_boarding` is unusable for step-free (it's NS's level-boarding flag).
  - Live lift status comes via SIRI-FM on NDOV's ZeroMQ stream. It is push-only, with a full snapshot once a day.

## In progress
- `audit/lift_listener.py` is logging the live lift feed to `data/raw/lifts/` for 72 h (started 29 Sep 21:12 CEST, stops about 2 Oct 21:12, or earlier if the PC sleeps).
  - **Next session:** analyse the logs. When does the daily full snapshot arrive? How many lifts are out? Then add the numbers to REPORT.md Q5.
  - Not blocking Phase 1.

## Next step
1. When Daan says go: start **Phase 1** (router + precompute) in `pipeline/`, as a new uv project on Python 3.12.
   - Reuse the audit's findings:
     - NS code as the key.
     - EPIAP per-track status: GTFS `platform_code` matches an EPIAP quay 98.7% of the time.
     - Apply `recommended_status` overrides.
     - Filter out NS's **"Drempelvrije bus"** routes (20 of them). GTFS files them as route_type 2 (rail), but they're buses, with stops like "[Bodegraven] OV halte…".
   - Log the +3 min transfer buffer in DECISIONS.md.
   - **Sprinter-only routes.** Daan added this to PLAN.md (Phase 1), plus a "sprinter / intercity" filter (Phase 2).
     - Precompute both variants ("sprinter only" and "all trains"); watch the output size.
     - What counts as a sprinter is NEEDS_DAAN item 2. Default until he answers: NS Sprinter + all regional operators' trains; no NS Intercity / Intercity direct / international.
     - Make the rule a config list, keyed on GTFS `route_short_name` category + agency.
2. Items waiting on Daan: see [NEEDS_DAAN.md](NEEDS_DAAN.md).
   - In-person Houten / Houten Castellum.
   - Optional NS API key.
   - Nextcloud `.git` ignore.

## How to resume
- Read `CLAUDE.md`, this file, `docs/PLAN.md`, then `audit/REPORT.md`.
- `cd audit && uv sync && uv run python run_all.py` rebuilds everything. Downloads are cached in `data/raw/`.
