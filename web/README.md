# web — the Trapvrij site

A static site (Vite + TypeScript + MapLibre GL). Pick an origin station and see which stations you can reach, filtered by profile, trains, day, changes and travel time. It has no backend: it reads the JSON files the pipeline builds.

## Run it

Needs Node 20.19+ (developed on 24) and a pipeline build (`cd pipeline && uv run python -m stepfree.build`).

```bash
npm install
npm run dev          # http://localhost:5173, data served from the pipeline build
npm test             # unit tests (vitest): search, results, URL state
npm run build:site   # type-check, build, and copy the data next to it
npm run preview      # serve the built site on http://localhost:4173
```

Paths come from the repo's `.env` (git-ignored), else the defaults:

| Setting | What | Default |
|---|---|---|
| `STEPFREE_BUILD` | pipeline output that `/data/*` is served from | `../data/build` |
| `STEPFREE_SITE` | where `build:site` writes the site | `web/dist` |

Locally both live outside Nextcloud (see `docs/DECISIONS.md`).

## What it loads

All from `/data/` (format in `pipeline/README.md`):

- `meta.json`: build date, the two timetable days, the time window.
- `stations.json`: every station with its step-free status per track, source, date and lifts.
- `origins/<CODE>.json`: travel times from one origin (about 10 KB compressed), fetched when that origin is chosen.
- `lifts.json`: current lift outages. **Optional** until Phase 3 builds it; without it the panel says live lift status is coming. Never write a placeholder "all lifts work" file: no data must look like no data.

## Code

| File | Does |
|---|---|
| `src/main.ts` | Wires everything: loads data, keeps the state, renders on change. |
| `src/state.ts` | The chosen origin and filters, mirrored in the URL hash (`#van=HTNC&overstap=2&max=alles`); defaults are left out. |
| `src/results.ts` | Turns an origin file plus the filters into one verdict per station (reachable, out of reach, not step-free, unknown). |
| `src/search.ts` | Station search that tolerates typos, accents and shorthand ("Utrecht CS", "A'dam", "Den Bosch"). |
| `src/combobox.ts` | The search box, following the WAI-ARIA combobox pattern. |
| `src/list.ts` | The results as a list: the accessible equivalent of the map. Also the legend. |
| `src/map.ts` | The map (loaded after the page). Travel time by colour; every other state by shape. |
| `src/panel.ts` | The station dialog: step-free status with source and date, the journey, lifts, links to NS to double-check. |
| `src/format.ts` | Dutch wording for durations, changes, frequencies and statuses. |
| `src/contact.ts` | The address for error reports, and mailto links with the subject filled in. |
| `src/colors.ts` | The travel-time colours for light and dark mode. |

`public/_redirects` makes `/station/<code>` serve the app on Cloudflare Pages. The path is reserved for destination pages; for now it opens that station.

## Rules the UI keeps

- **Never colour alone.** Travel time is a blue ramp of five bands; the other states have their own shapes, and the legend and list say everything in words.
- **Unknown is not step-free.** With a pram, stations with unknown access are shown as such and never counted as reachable.
- **The list works without the map.** If the tiles or WebGL fail, a note replaces the map.
- **No cookies, no storage, no tracking.** State lives in the URL only. The tiles (OpenFreeMap) set no cookies either.
- **Dutch UI**, code and comments in English.

## Accessibility checks

- Lighthouse, against `npm run preview`:
  `npx lighthouse http://localhost:4173/ --only-categories=accessibility --chrome-flags="--headless=new"`.
  On 2026-09-30 it scored 100 on the start page, an origin view (`/#van=HTNC`) and a station page (`/station/UT`).
- axe-core: inject `node_modules/axe-core/axe.min.js` into the page and run `axe.run()`. There were 0 violations in light, dark and a 375 px phone layout.
- By hand: the whole flow works with the keyboard alone (search, filters, list, dialog, Escape to close).
