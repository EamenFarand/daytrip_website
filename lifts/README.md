# lifts — live lift status for Trapvrij (and which trains run without steps)

A small listener for Daan's home server. It does two things, both from NDOV Loket's open data (CC0):
- It follows the live lift feed (SIRI-FM) and keeps Cloudflare up to date with which lifts are out of order. The site reads that through `functions/api/lifts.js`.
- It follows NS's journey messages (InfoPlus RIT), in which NS marks every train unit accessible or not. It keeps a record of which trains ran with accessible units only. The build reads that through `functions/api/trains.js` to decide which trains count as "without steps" (`docs/DECISIONS.md`, 2026-10-07).

Why it works this way: `docs/DECISIONS.md` (2026-10-02) and `audit/REPORT.md` Q5. The short version:
- The feed is a push stream: the status of all lifts every night around 04:02, and changes as they happen.
- Fetching it now and then misses changes, so something has to listen all the time.

## What it does

- Holds **one** connection to the feed (NDOV Loket's fair-use rule), so run it in one place only.
- Keeps every lift's status. The 04:02 full status replaces everything, and changes are added as they come.
- Keeps a lift that came back less than 30 minutes ago on the list, as `back`: lifts often fail again soon after (`docs/DECISIONS.md`, 2026-10-04). The site words it as "net weer in gebruik".
- Saves that state in a Docker volume, so a restart carries on where it stopped.
- Publishes to Cloudflare when the set of broken lifts changes (at most every 2 minutes), and at least every 10 minutes, so the site can see it's alive.
- Never publishes something implausible: no full status yet, fewer than 300 lifts, or more than half out. The site then shows the last good status until it's too old, and after that "unknown".
- **Trains:** a second connection, to a different stream (so still one per stream).
  - Per service date it keeps which train numbers ran with accessible units only, and which with at least one that isn't. One unit that isn't is enough for that day.
  - It keeps 35 days, saved every 10 minutes (`trains.json` in the volume), and publishes them every hour under the key `trains` in the same store.
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

In the log you should see two lines: `connected to tcp://pubsub.besteffort.ndovloket.nl:7666` (lifts) and `connected to tcp://pubsub.besteffort.ndovloket.nl:7664` (trains).

**Until the first full status arrives, it doesn't publish lifts.** That happens at around 04:02 at night. Before then it logs `not publishing: no full state yet`, which is expected. After that, it logs `published: 50 of 443 lifts out, 1 just back` whenever a lift changes (at most every 2 minutes), and at least every 10 minutes.

Trains go out within a minute of starting, then every hour: `trains published: 12 days; yesterday 5812 trains, 4903 with accessible units only`.

To test without publishing, put `DRY_RUN=1` in `.env`: it then writes `/data/lifts.json` and `/data/trains-out.json` inside the volume instead.

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

CI runs the same tests and checks that the image builds (`.github/workflows/test.yml`). `testdata/` holds three real journey messages of 7 Oct 2026 (NDOV Loket, CC0): a five-car ICNG (accessible), the ICNG built for Brussels (not), and double-deckers.
