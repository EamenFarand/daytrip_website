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

## Cloudflare: the store and its key

Done once, on 3 Oct 2026. Repeat step 2 only to replace the key.

1. **The store:** in the Cloudflare dashboard, *Storage & Databases → Workers KV → Create*, named `trapvrij-lifts`. Its ID goes in `.env` here, and in `wrangler.toml` at the repo root (binding `LIFTS`), which connects it to the site.
2. **The key:** profile icon → *My Profile → API Tokens → Create Token*, then *Custom token*:
   - name `trapvrij-lifts-writer`;
   - permissions: one row, **Account · Workers KV Storage · Edit**, nothing else;
   - account resources: your account;
   - no IP filter (a home IP can change) and no expiry.

   Copy it at once; it's shown only once, and it goes only in `.env` on the server.
3. **The account ID:** on *Workers & Pages* (right-hand side), and in the dashboard's web address.

## Install (Linux with Docker)

You need the three values from the section above.

```bash
git clone https://github.com/EamenFarand/daytrip_website.git trapvrij
cd trapvrij/lifts
cp .env.example .env
nano .env               # fill in the three values
docker compose up -d --build
docker compose logs -f  # Ctrl+C stops watching; the listener keeps running
```

In the log you should see `connected to tcp://pubsub.besteffort.ndovloket.nl:7666`.

**Until the first full status arrives, it doesn't publish.** That happens at around 04:02 at night. Before then it logs `not publishing: no full state yet`, which is expected. After that, it logs `published: 50 of 443 lifts out` whenever a lift changes (at most every 2 minutes), and at least every 10 minutes.

To test without publishing, put `DRY_RUN=1` in `.env`: it then writes `/data/lifts.json` inside the volume instead.

## Day to day

| What | Command (in `trapvrij/lifts`) |
|---|---|
| Is it running? | `docker compose ps` |
| What is it doing? | `docker compose logs --tail 50` |
| Update after a change in the repo | `git pull && docker compose up -d --build` |
| Stop | `docker compose down` (the saved state stays in the volume) |

It restarts by itself after a crash or a reboot (`restart: unless-stopped`). Log times are UTC: Dutch time minus 2 hours in summer, minus 1 in winter.

## Development

```bash
uv sync && uv run pytest
```

CI runs the same tests and checks that the image builds (`.github/workflows/test.yml`).
