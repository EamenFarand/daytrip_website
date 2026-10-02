# Status

*Last updated: 2026-10-02 (session 3)*

## Where we are
**Phases 0–2 are done, and the launch setup is in place and checked.** We're waiting only for Daan's go for Phase 3 (NEEDS_DAAN 1).
- **Name and domain:** *Trapvrij* on `trapvrij.nl`, registered at TransIP. The site and docs use the name.
  - On 2 Oct Daan moved the nameservers to Cloudflare, with DNSSEC off first. Cloudflare answers for the zone.
  - Left: Cloudflare marks the zone active, then DNSSEC goes back on via Cloudflare (NEEDS_DAAN 2).
  - This doesn't block Phase 3: the site launches on `*.pages.dev` first.
- **Live lift status, decided:** a Docker listener on Daan's home server writes to Cloudflare KV, and a tiny Pages Function serves it. See DECISIONS 2026-10-02 and PLAN Phase 3; Daan's setup steps are in NEEDS_DAAN 3.
- **Error reports** go to deonw_W@hotmail.com: on the about page, plus a "Meld het" link in each station panel with the station in the subject.
- **Cloudflare:** both deploy secrets are set in GitHub and verified by the workflow *Check Cloudflare secrets*: an active token with Pages access, 0 projects so far.
- **PLAN.md** was expanded by Daan on 2026-10-01: live lift status, pre-rendered station pages, and a housekeeping item (now corrected in NEEDS_DAAN 8).

## Done
- **Phase 0**: data audit, verdict Go. See `audit/REPORT.md`.
- **Phase 1**, in `pipeline/` (see `pipeline/README.md`):
  - `uv run python -m stepfree.build` builds `meta.json`, `stations.json` and 395 `origins/<CODE>.json`. It takes about 2.5 min on 4 cores; output is 32 MB (about 10 KB compressed per origin).
  - Router: platform-level range RAPTOR, with the stroller profile enforced during the search, both train sets (all / sprinter), 08:30–12:00, 0/1/2 changes. The days are re-chosen each build: now Wed 28 Oct and Sat 24 Oct.
  - More options never look worse (fixed 2026-09-30 after Daan's report):
    - Each entry is the best of its own and those with fewer options: fewer changes, sprinters only, or the pram profile.
    - Before the fix, Utrecht C within 30 min gave 40 stations direct but 35 with a change allowed.
  - The build → validate → swap step blocks broken output:
    - on the raw router output: more options are never slower;
    - on the files: structure, never a longer typical time with more options, and known answers.
  - Tests: `uv run pytest`, 53 passing and 1 skipped (NS API).
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

## Lift feed (analysed 2026-10-02)
The 72-hour log is done; it's in `<cache>/lifts/` (moved out of Nextcloud). See `audit/REPORT.md` Q5 and `audit/lift_analysis.py`.
- The full state of all 443 lifts arrives every night at 04:02. Changes are pushed within minutes, about 200 real ones a day.
- The change stream went silent on 2 Oct after 00:55 and was still silent at 20:28, while heartbeats continued.
- Daan chose the home-server listener (option b). Asking NDOV Loket about the silence is optional (NEEDS_DAAN 4).

## Next step
1. Daan's go for Phase 3 (NEEDS_DAAN 1).
2. **Phase 3** (see PLAN.md):
   - A GitHub Actions nightly job: fetch with conditional GET, build only if the feeds changed, validate, deploy with `wrangler pages deploy`. Keep the last good build when validation fails. Run the pipeline and web tests in CI.
   - Lift status, the `lifts/` listener for Daan's home server:
     - Python, Docker and compose. It resets on the 04:02 full state and applies changes.
     - It writes `lifts.json` to KV, validated, when something changes (at most every 2 minutes). Never a placeholder file.
     - A read-only Pages Function serves it.
     - The site falls back to "status as of 04:02" after about 30 minutes without messages, and to "unknown" when the last full state is more than about 26 hours old.
     - Daan then creates the KV store and its key, and runs the container (NEEDS_DAAN 3).
   - Lift warnings on the whole journey: origin, transfers and destination.
   - Pre-rendered station pages, `sitemap.xml`, canonical URLs.
   - Connect `trapvrij.nl` once Cloudflare has activated the zone (NEEDS_DAAN 2).
   - Mind two GitHub limits: scheduled workflows in a public repo pause after 60 days without repo activity, and `ubuntu-latest` moves to Ubuntu 26 from 19 Oct 2026.
3. When the NS API key arrives: `cd pipeline && uv run python -m stepfree.ns_check`. Investigate any route off by more than 5 min.

## How to resume
- Read `CLAUDE.md`, this file, `docs/PLAN.md`, `docs/DECISIONS.md` (newest first), `pipeline/README.md` and `web/README.md`.
- Pipeline: `cd pipeline && uv sync && uv run pytest && uv run python -m stepfree.build`. Downloads are cached; paths come from `.env`.
- Web: `cd web && npm install && npm test && npm run dev`.
- If `.env` is missing (fresh checkout), everything goes to `data/raw`, `data/build` and `web/dist`, which is fine outside Nextcloud.
