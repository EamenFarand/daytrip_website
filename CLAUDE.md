# Trapvrij (trapvrij.nl)

A map-based web tool: pick any Dutch railway station as origin and see which stations you can reach **step-free** — with a pram in v1, wheelchair later — filtered by number of changes and travel time. Later, each destination gets a "what to do here with a pram" page.

## Why this exists
The NS app answers "can I get from A to B accessibly?". Nothing answers "I'm at A with a pram — where can I go?". That exploration question is the product.

## Who you're working with
Daan owns this project. He does only what an AI can't: create accounts, supply API keys, buy the domain, make payments, check stations in person (he's near Houten / Utrecht), and make go/no-go calls. Everything else is yours. He is also using this project to get better at directing AI, so leave a clear trail (see Working agreements).

## Principles
1. **Conservative by default.** Unknown accessibility = not step-free. Show it as "unknown"; never guess. A wrong "yes" strands someone on a platform; a wrong "no" only costs a suggestion.
2. **Runtime without AI.** Everything that runs after launch is plain code on free infrastructure (GitHub Actions, Cloudflare Pages). Target running cost: €0/month, excluding the domain.
3. **Boring tech, small steps.** Prefer simple, well-known tools. Commit working increments with clear messages.
4. **Respect data sources.** Follow each source's licence and terms, cache downloads, rate-limit requests, and never scrape a site whose terms forbid it. Credit every source on the site.
5. **No implied affiliation.** No NS, ProRail or operator logos or brand styling, and don't name the product after them.
6. **The site itself must be accessible** (WCAG 2.2 AA) and work well on a phone — most users will be standing on a platform with one free hand.

## Stack (defaults — change only with a reason logged in DECISIONS.md)
- Data pipeline: Python 3.12, `uv`, pandas or polars, pytest
- Frontend: static site — Vite + TypeScript + MapLibre GL JS
- Hosting: Cloudflare Pages. Scheduled jobs: GitHub Actions
- Live lift status: a Docker listener on Daan's always-on Linux home server writes to Cloudflare Workers KV, and a tiny read-only Pages Function serves it (see DECISIONS.md, 2026-10-02). The same listener records which trains NS marks accessible, for the build (DECISIONS.md, 2026-10-07)
- Secrets: `.env` locally (git-ignored), GitHub Actions secrets in CI, an env file on the home server. Never commit keys.

## Layout
- `pipeline/` — fetching, cleaning, routing, precompute
- `web/` — frontend
- `lifts/` — the lift-status listener for the home server (Phase 3)
- `data/raw/` (git-ignored) and `data/build/` (what the site loads)
- `audit/` — Phase 0 data audit
- `docs/` — PLAN.md, STATUS.md, DECISIONS.md, NEEDS_DAAN.md

## Working agreements
- **`docs/PLAN.md` is the plan.** Work phase by phase. At the end of each phase, stop and summarise for Daan before starting the next.
- **`docs/STATUS.md`** — update at the end of every session: done, in progress, next step. A fresh session must be able to continue from this file alone.
- **`docs/DECISIONS.md`** — one short entry per non-obvious decision: what, why, what you rejected.
- **`docs/NEEDS_DAAN.md`** — batch everything that needs Daan (accounts, keys, purchases, in-person checks, decisions) here with exact step-by-step instructions, rather than stopping for each one. Keep working on whatever doesn't depend on it.
- Code, comments and docs in English. Site UI in Dutch (the default, at `/`) and English (under `/en/`): every text in both.
