# web — the Trapvrij site

A static site (Vite + TypeScript + MapLibre GL). Pick an origin station and see which stations you can reach, filtered by profile, trains, day, changes and travel time. It has no backend: it reads the JSON files the pipeline builds.

## Run it

Needs Node 20.19+ (developed on 24) and a pipeline build (`cd pipeline && uv run python -m stepfree.build`).

```bash
npm install
npm run dev          # http://localhost:5173, data served from the pipeline build
npm test             # unit tests (vitest): search, results, URL state, lifts, both languages, the pages
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
- `origins/<CODE>.json`: travel times from one origin (about 20 KB compressed), fetched when that origin is chosen.

And the live lift status from `/api/lifts`. In production that's `functions/api/lifts.js`, reading what the home-server listener (`lifts/`) writes to Cloudflare KV. Locally, the dev and preview servers serve the file named by `STEPFREE_LIFTS` in `.env`, or 404. No data means "lift status unknown": never write a placeholder "all lifts work".

## Pages

`npm run build:site` builds the app, copies the data, then runs `scripts/pages.ts`. That script writes, from the data, in Dutch and under `/en/` in English:
- `/station/<slug>/` for every station: its own title, description and canonical URL, and an intro that works without JavaScript. The app on that page starts from that station.
- `/station/`: all stations as plain links.
- `404.html` (and `/en/404.html`: Cloudflare Pages serves the nearest one).
- Once, for both languages: `sitemap.xml`, and `_redirects` (old `/station/<CODE>` links go to the page).

## Two languages

Dutch is the default at `/`; English lives under `/en/` (DECISIONS 2026-10-07).
- **Two page shells:** `index.html` and `en/index.html`. Change both: a test (`src/i18n.test.ts`) checks they have the same elements in the same order.
- **One app:** it reads `<html lang>`. Texts in the code are `{ nl, en }` pairs passed to `tr()` (`src/i18n.ts`), so a missing translation doesn't type-check. `scripts/pages.ts` switches the language with `useLang()` per page it writes.
- **The switch** ("NL | EN" in the header) links to the same page and view in the other language. The hash keys are the same in both languages, so links work in either.
- **Wording:** British English; "pram" for kinderwagen, "platform" for spoor (as NS's English site does). Links to NS go to its English pages.
- No language detection and nothing remembered: the URL is the choice.

## Code

| File | Does |
|---|---|
| `src/main.ts` | Wires everything: loads data, keeps the state, renders on change. |
| `src/state.ts` | The chosen origin (in the path, `/station/<slug>/` or `/en/station/<slug>/`) and filters (in the hash, `#overstap=2&max=alles`); defaults are left out, and old `#van=` links still work. |
| `src/lifts.ts` | How fresh the lift status is, which lifts out matter for a journey (the tracks it uses), and the words for each status (out, unknown, just back). |
| `src/results.ts` | Turns an origin file plus the filters into one verdict per station (reachable, out of reach, not step-free, unknown). |
| `src/search.ts` | Station search that tolerates typos, accents and shorthand ("Utrecht CS", "A'dam", "Den Bosch"). |
| `src/combobox.ts` | The search box, following the WAI-ARIA combobox pattern. |
| `src/list.ts` | The results as a list: the accessible equivalent of the map. Also the legend. |
| `src/map.ts` | The map (loaded after the page). Travel time by colour; every other state by shape. |
| `src/panel.ts` | The station dialog: step-free status with source and date, the journey, lifts, links to NS to double-check. A journey that relies on an intercity without steps (usually the ICNG) gets a note that NS sometimes runs another train. |
| `src/format.ts` | Wording for durations, changes, frequencies, dates and statuses, in the page's language. |
| `src/i18n.ts` | The page's language, `tr()` for `{ nl, en }` texts, and the path of a page in the other language. |
| `src/contact.ts` | The address for error reports, and mailto links with the subject filled in. |
| `src/colors.ts` | The travel-time colours for light and dark mode. |

`scripts/pages.ts` writes the pre-rendered pages (see Pages). `public/_headers` sets security headers and caching for Cloudflare Pages.

## Rules the UI keeps

- **Never colour alone.** Travel time is a blue ramp of five bands; the other states have their own shapes, and the legend and list say everything in words.
- **Unknown is not step-free.** With a pram, stations with unknown access are shown as such and never counted as reachable.
- **Trains without steps** ("Zonder trapjes", the `sprinter` set) follow NS's own mark per train; the pipeline decides (DECISIONS 2026-10-07).
- **The list works without the map.** If the tiles or WebGL fail, a note replaces the map.
- **No cookies, no storage.** State lives in the URL only. The tiles (OpenFreeMap) set no cookies either. Visits are counted anonymously with Cloudflare Web Analytics, which sets no cookies either; the footer says so. Cloudflare adds its script itself, so there's no code for it here.
- **Dutch and English UI**, every text in both; code and comments in English.

## Accessibility checks

- Lighthouse, against `npm run preview`:
  `npx lighthouse http://localhost:4173/ --only-categories=accessibility --chrome-flags="--headless=new"`.
  On 2026-09-30 it scored 100 on the start page, an origin view (`/#van=HTNC`) and a station page (`/station/UT`).
- axe-core: inject `node_modules/axe-core/axe.min.js` into the page and run `axe.run()`. There were 0 violations in light, dark and a 375 px phone layout.
- By hand: the whole flow works with the keyboard alone (search, filters, list, dialog, Escape to close).
