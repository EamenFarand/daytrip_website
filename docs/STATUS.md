# Status

*Last updated: 2026-10-07 (session 3)*

## Where we are
**Phase 3 is under way, and the site is live at <https://trapvrij.nl>** (www and http redirect there), with DNSSEC since 3 Oct (checked from outside). Daan gave the go on 2 Oct.
Built and running:
- CI on every push;
- the twice-daily build and deploy;
- station pages;
- the lift listener on Daan's server (publishing since 4 Oct, 04:02) and the site's lift warnings.

Nothing from Daan blocks v1. The listener runs the new code since 4 Oct (20:10 UTC), and the first lift that came back showed correctly on the live site.
Search Console: domain verified and sitemap submitted on 3 Oct.


## Phase 3: done
- **CI:** `.github/workflows/test.yml` runs on every push:
  - pipeline pytest;
  - web: tsc and vitest;
  - lifts: pytest, and checks that the Docker image builds.
- **Build and deploy:** `.github/workflows/deploy.yml`.
  - Runs at 05:40 and 15:10 UTC, on pushes to main, and by hand.
  - On the schedule it stops if the inputs (`stepfree.inputs`: hashes of the sources, corrections and code) match the live build's and no timetable day has passed.
  - Then: build (validated), tests against the real build, site build, project check, publish, and a check that the live site serves the new build. The run takes under 4 minutes.
  - A failure publishes nothing; the last good deployment stays live.
  - Downloads are cached between runs (conditional GETs).
  - The build's workers start with "spawn" (fork deadlocked with polars on Linux).
- **Station pages** (`web/scripts/pages.ts`, run in `build:site`):
  - `/station/<slug>/` for all 395 stations: own title, description, canonical and Open Graph tags, and an intro that works without JavaScript (status, lifts, what you reach within 30/60 min, linked).
  - Also `/station/` (all stations), `sitemap.xml`, `_redirects` for old `/station/<CODE>` links, and `404.html`.
  - The app takes the origin from the path.
  - Lighthouse on the live site (home, `/station/`, 4 station pages): accessibility 100, SEO 100.
- **Live lift status:**
  - `lifts/` has the listener (Docker, for Daan's home server; state saved, plausibility checks, KV writes) and its README.
  - `functions/api/lifts.js` serves the KV value read-only. It returns 404 until there is one, and the site then shows "unknown".
  - The site has three freshness levels: live, "as of 04:02" after 30 min silence, and unknown after 26 h.
  - Warnings cover origin, changes and destination, only for lifts serving the tracks the typical journey uses (the build now stores those tracks). They show in the panel, next to change stations, and on list entries, and refresh every 5 min.
  - Live since 4 Oct: the full status arrived at 04:02, then a publish every few minutes. Checked with real data: `/api/lifts`, the station panels, and the warnings (10 of Houten's destinations).
  - The about box explains the lift status (what it shows, the source, about ten minutes' delay, that it can be out of date), and the sources credit it.
  - A lift that has just come back keeps a softer warning for 30 minutes (Daan's choice A, DECISIONS 2026-10-04): the listener lists it as `back`, and the site says "net weer in gebruik". Site and listener have it since 4 Oct; checked live with UT-LIF-009 (Utrecht Centraal).
- Also: the softer dark mode, the name Trapvrij, and a report link per station. Reports go to `meld@trapvrij.nl` (Cloudflare Email Routing) since 3 Oct.
- **English version** (7 Oct, Daan's request, DECISIONS 2026-10-07):
  - every page also exists under `/en/` (home, 395 station pages, `/en/station/`, `/en/404.html`);
  - a "NL | EN" switch in the header leads to the same page and view;
  - `hreflang` links connect the twins, and the sitemap lists both languages (794 pages);
  - texts are `{ nl, en }` pairs in the code (`web/src/i18n.ts`), and a test keeps the two page shells identical in structure;
  - checked locally: both directions of the switch, the station panel, phone width, light and dark, and axe with 0 violations on 6 pages;
  - live since 7 Oct, about 21:00, and checked on trapvrij.nl:
    - both languages, with the right `lang`, canonical and switch target;
    - the English 404 page under `/en/`;
    - the sitemap (794 pages);
    - English lift warnings with real data.
- **Visit counts:** Cloudflare Web Analytics, switched on for the Pages project; Cloudflare adds its script to each page on deploy (not to the 404 page). Checked 3 Oct on the live site: no cookies, nothing in browser storage. The footer says so (DECISIONS, 2026-10-03).

## Phase 3: left
1. Done 4 Oct: Daan updated the listener, and a lift that came back (UT-LIF-009) showed on the live site as "net weer in gebruik". NEEDS_DAAN now holds only optional items or ones waiting on others.
2. Done 4 Oct: the store is connected (`wrangler.toml`, binding `LIFTS`), the listener publishes, and `/api/lifts` and the warnings are checked with real data.
3. Done 3 Oct: `SITE_URL` in `deploy.yml` is `https://trapvrij.nl`; the site, redirects and canonical URLs work there.
4. Done 4 Oct: the lift text in the about box (PLAN.md, housekeeping).
5. **About two weeks after the sitemap (around 17 Oct):** ask Daan for Search Console's indexing report and fix what it flags (PLAN.md, housekeeping).
6. **v1 definition of done:** nightly pipeline green for 7 consecutive days, counted once the domain is live. 3–5 Oct and the 6 Oct morning run were green; the 6 Oct evening and 7 Oct runs failed (Wolfheze closed on the chosen days; fixed 7 Oct, DECISIONS). The count starts again from the first green day after the fix.
7. **GitHub limits:**
   - Scheduled workflows in a public repo pause after 60 days without repo activity: add a keep-alive, or note it for Daan.
   - `ubuntu-latest` moves to Ubuntu 26 from 19 Oct; we pin `ubuntu-24.04`.
8. Then stop and summarise Phase 3 for Daan.

**Waiting for Daan (not part of v1):** trains without steps from NS's own data, which would bring in the ICNG intercities (NEEDS_DAAN 1).
- NS's InfoPlus journey messages (`/RIG/InfoPlusRITInterface5` on `pubsub.besteffort.ndovloket.nl:7664`, CC0) give every train unit a type and NS's flag `MaterieelDeelToegankelijk` (J/N).
- A 3-minute sample on 7 Oct also flagged some regional trains the site now counts as step-free as "N" (Arriva LINT, NMBS Roosendaal–Antwerpen).

## Done before
- **Phase 0**: data audit, verdict Go. See `audit/REPORT.md`, including Q5 on the 72-hour lift log.
- **Phase 1**, in `pipeline/` (see `pipeline/README.md`):
  - `uv run python -m stepfree.build` builds `meta.json`, `stations.json` and 395 `origins/<CODE>.json` in about 2 minutes on 4 cores, 44 MB.
  - Router: platform-level range RAPTOR, with the stroller profile enforced during the search, both train sets, 08:30–12:00, 0/1/2 changes. The days are re-chosen each build: the Tue/Wed/Thu and the Saturday with the most regular stations served, then the most stops, within eight weeks (DECISIONS 2026-10-07). Now Wed 4 Nov and Sat 21 Nov.
  - More options never look worse: each entry is the best of its own and those with fewer options.
  - Validation runs on the raw router output (more options never slower) and on the files (structure, typical time, page names, tracks, known answers).
  - Tests: `uv run pytest`, 60 passing and 1 skipped (NS API).
- **Phase 2**, in `web/` (see `web/README.md`):
  - search, filters, a map by travel time and shape, the list, the station panel, and URL state;
  - no cookies;
  - Lighthouse accessibility 100 and axe 0 violations;
  - unit tests: 63 since the English version.

## Known limitations (fine for now)
- Lighthouse performance on the live site is 56–85 (mobile, slow 4G).
  - Station pages show their text within about 1 s.
  - The home page waits for data, and MapLibre needs about 0.6–0.9 s of main thread.
  - Possible later: preload the data, start the map when idle.
- Lift warnings use the typical journey's tracks; other departures can use other tracks (DECISIONS).
- The map markers are small; the list is the accessible equivalent (WCAG 2.5.8).
- A station closed for longer than the build looks ahead (eight weeks) drops out of the build, and so does its page, for that time.
- GitHub starts the scheduled builds hours late (3–4 Oct: around 10:40 and 18:40 UTC instead of 05:40 and 15:10). The data still refreshes daily, and with two runs a day a dropped run is covered.

## How to resume
- Read `CLAUDE.md`, this file, `docs/PLAN.md`, `docs/DECISIONS.md` (newest first), `pipeline/README.md`, `web/README.md` and `lifts/README.md`.
- Pipeline: `cd pipeline && uv sync && uv run pytest && uv run python -m stepfree.build`. Downloads are cached; paths come from `.env`.
- Web: `cd web && npm install && npm test && npm run dev`, or `npm run build:site` and the "web-preview" server.
  - Locally, `/api/lifts` serves the file named by `STEPFREE_LIFTS` in `.env` (a test file made from the lift log), or 404.
- Lifts: `cd lifts && uv sync && uv run pytest`.
- CI status: `gh run list -R EamenFarand/daytrip_website`.
