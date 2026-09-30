# Status

*Last updated: 2026-09-30 (end of session 2)*

## Where we are
**Phase 2 (map frontend) is done.** Waiting for Daan to review the site and give the go for Phase 3 (NEEDS_DAAN item 1).
Phases 0 and 1 are done. Phase 3 needs a name and domain, a report email and a Cloudflare deploy key from Daan (NEEDS_DAAN items 2–4); nothing else blocks it.

## Done
- **Phase 0**: data audit, verdict Go. See `audit/REPORT.md`.
- **Phase 1**, in `pipeline/` (see `pipeline/README.md`):
  - `uv run python -m stepfree.build` builds `meta.json`, `stations.json` and 395 `origins/<CODE>.json`. It takes about 2.5 min on 4 cores; output is 34 MB (about 10 KB compressed per origin).
  - Router: platform-level range RAPTOR, with the stroller profile enforced during the search, both train sets (all / sprinter), weekday Wed 21 Oct and Saturday 24 Oct, 08:30–12:00, 0/1/2 changes.
  - The build → validate → swap step blocks broken output: structural checks, invariants (pram never faster, sprinter never faster, more changes never slower) and known answers.
  - Tests: `uv run pytest`, 46 passing and 1 skipped (NS API).
  - Corrections file `pipeline/overrides/stations.csv`: Houten, Houten Castellum, Den Haag C and Groningen confirmed by Daan, plus the audit's conservative corrections.
- **Phase 2**, in `web/` (see `web/README.md`):
  - Vite + TypeScript + MapLibre 6.
    - Run: `npm --prefix web run dev` (or the "web" entry in `.claude/launch.json`).
    - Data is served from `STEPFREE_BUILD`. The built site goes to `STEPFREE_SITE`: `npm --prefix web run build:site`, preview with "web-preview".
  - Station search that tolerates typos and abbreviations; filters for profile (wheelchair shown as "komt later"), trains, day, changes and time, folded on phones.
  - Map coloured by travel time, other states by shape; a list as the accessible equivalent; a station panel with source, date, lifts and NS links; `/station/<code>` works.
  - State lives in the URL hash only. There are no cookies; the tiles set none either (checked).
  - The map is lazy-loaded: 9 KB of page script compressed, then MapLibre.
  - Checks:
    - Lighthouse accessibility **100** on four views (start, an origin, a station page, an origin a pram can't use); SEO 100; best practices 96.
    - axe-core: 0 violations in light, dark and phone layouts.
    - The full flow works by keyboard. The session 2 walk-through found and fixed a bug: the skip link used to wipe the chosen origin.
    - `npm test`: 35 tests.
    - Four routes spot-checked against the NS planner website: all match.
  - Decisions are logged in `docs/DECISIONS.md` (tiles, colours and shapes, list, URL state, defaults, lazy map, search, lift data).
- Housekeeping: the download cache, data build and site build live outside Nextcloud via `.env` (`STEPFREE_CACHE`, `STEPFREE_BUILD`, `STEPFREE_SITE`).

## Known limitations (fine for now)
- Every page load logs a 404 for `/data/lifts.json`; Phase 3 creates that file. This is the only reason best practices scores 96.
- MapLibre takes about 0.9 s of main thread to start on a throttled phone, so Lighthouse performance is 79–80 (mobile, slow 4G). The list is usable before that.
- The map markers are small; the list is the accessible equivalent (WCAG 2.5.8).

## In progress
- `audit/lift_listener.py` is logging the live lift feed to `data/raw/lifts/` until about 2 Oct 21:12.
  - Next session: analyse it. When does the daily full snapshot arrive, and how many lifts are out? Add the answers to `audit/REPORT.md` Q5.
  - Then move `data/raw/lifts` to the cache folder too.

## Next step
1. Daan reviews the site (NEEDS_DAAN 1). Make any changes he asks for.
2. After his go, **Phase 3**:
   - A GitHub Actions nightly job: fetch with conditional GET, build only if the feeds changed, validate, deploy with `wrangler pages deploy`. It needs the Cloudflare secrets (NEEDS_DAAN 4).
   - Lift status into `lifts.json`. First decide how, using the listener analysis: the feed is a ZeroMQ push stream, so a short scheduled job only sees changes plus the daily full snapshot. Never write a placeholder file (DECISIONS).
   - Keep the last good build when validation fails.
   - About page: the report email (NEEDS_DAAN 3). The final name and domain (NEEDS_DAAN 2).
   - Run the pipeline and web tests in CI.
3. When the NS API key arrives: `cd pipeline && uv run python -m stepfree.ns_check`. Investigate any route off by more than 5 min.

## How to resume
- Read `CLAUDE.md`, this file, `docs/PLAN.md`, `docs/DECISIONS.md` (newest first), `pipeline/README.md` and `web/README.md`.
- Pipeline: `cd pipeline && uv sync && uv run pytest && uv run python -m stepfree.build`. Downloads are cached; paths come from `.env`.
- Web: `cd web && npm install && npm test && npm run dev`.
- If `.env` is missing (fresh checkout), everything goes to `data/raw`, `data/build` and `web/dist`, which is fine outside Nextcloud.
