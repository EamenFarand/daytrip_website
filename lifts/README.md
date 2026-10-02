# lifts — live lift status for Trapvrij

A small listener for Daan's home server. It follows the live lift feed (SIRI-FM via NDOV Loket, CC0) and keeps Cloudflare up to date with which lifts are out of order. The site reads that through `functions/api/lifts.js`.

Why it works this way: `docs/DECISIONS.md` (2026-10-02) and `audit/REPORT.md` Q5. The short version:
- The feed is a push stream: the status of all lifts every night around 04:02, and changes as they happen.
- Fetching it now and then misses changes, so something has to listen all the time.

## What it does

- Holds **one** connection to the feed (NDOV Loket's fair-use rule), so run it in one place only.
- Keeps every lift's status. The 04:02 full status replaces everything, and changes are added as they come.
- Saves that state in a Docker volume, so a restart carries on where it stopped.
- Publishes to Cloudflare when the set of broken lifts changes (at most every 2 minutes), and at least every 10 minutes, so the site can see it's alive.
- Never publishes something implausible: no full status yet, fewer than 300 lifts, or more than half out. The site then shows the last good status until it's too old, and after that "unknown".
- Only makes outgoing connections; nothing on your network is opened up.

## Install (Linux with Docker)

You need the Cloudflare account ID, the key-value store's ID and its key (see `docs/NEEDS_DAAN.md`).

```bash
git clone https://github.com/EamenFarand/daytrip_website.git trapvrij
cd trapvrij/lifts
cp .env.example .env
nano .env               # fill in the three values
docker compose up -d --build
docker compose logs -f  # Ctrl+C stops watching; the listener keeps running
```

In the log you should see `connected to tcp://pubsub.besteffort.ndovloket.nl:7666`.

**Until the first full status arrives, it doesn't publish.** That happens at around 04:02 at night. Before then it logs `not publishing: no full state yet`, which is expected. After that, it logs `published: 56 of 443 lifts out` about every 10 minutes.

To test without publishing, put `DRY_RUN=1` in `.env`: it then writes `/data/lifts.json` inside the volume instead.

## Day to day

| What | Command (in `trapvrij/lifts`) |
|---|---|
| Is it running? | `docker compose ps` |
| What is it doing? | `docker compose logs --tail 50` |
| Update after a change in the repo | `git pull && docker compose up -d --build` |
| Stop | `docker compose down` (the saved state stays in the volume) |

It restarts by itself after a crash or a reboot (`restart: unless-stopped`).

## Development

```bash
uv sync && uv run pytest
```

CI runs the same tests and checks that the image builds (`.github/workflows/test.yml`).
