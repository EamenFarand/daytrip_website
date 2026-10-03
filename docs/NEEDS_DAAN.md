# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

The site is live at **<https://trapvrij.nl>**, with DNSSEC. Item 1 is what's left from you for v1: confirming the lift listener publishes.

### 1. Run the lift listener on your home server

**Status 3 Oct:** the listener runs on your server since 10:02 (log: connected, waiting for the full status), and the store `trapvrij-lifts` is connected to the site (`wrangler.toml`; `/api/lifts` answers 404 = connected but empty). **Left:** after about 04:02 tonight, check that the log says `published: …` (part B, step 6) and tell me; I'll check the site.

The code is ready: [lifts/README.md](../lifts/README.md). CI checks that its Docker image builds. Until it runs, the site says the lift status is unknown.

**Part A, in the Cloudflare dashboard** (any computer):
1. **Create the store.**
   1. In the left menu, open *Storage & Databases → Workers KV* (in some versions it's under *Workers & Pages → KV*).
   2. Click *Create* and name it `trapvrij-lifts`.
   3. Copy its **ID**: 32 letters and digits, shown in the list of stores.
2. **Create the second key** (a separate one; leave the deploy key alone):
   1. Click your profile icon at the top right, then *My Profile → API Tokens → Create Token*.
   2. At the bottom, under *Custom token*, click *Get started*.
   3. *Token name:* `trapvrij-lifts-writer`.
   4. *Permissions:* one row, chosen from the three dropdowns: **Account** · **Workers KV Storage** · **Edit**. Nothing else.
   5. *Account Resources:* **Include** · your account.
   6. *Client IP Address Filtering:* leave it empty. Your home IP can change, and the listener would then stop.
   7. *TTL:* leave it empty, so the key doesn't expire.
   8. Click *Continue to summary → Create Token*, and copy the token right away; it's only shown once. Keep it for part B. It goes only into the settings file on your server, never into GitHub or this chat.
3. **Send me the store's ID** (not the token). The ID isn't secret. I'll connect the store to the site.

**Part B, on the server** (in a terminal on the machine itself, or over SSH):
1. **Check that git and Docker are there:**
   ```bash
   git --version && docker --version && docker compose version
   ```
   - If `docker compose` isn't found but `docker-compose` is, use `docker-compose` (with a dash) in the commands below.
   - If Docker says *permission denied*, put `sudo` in front of each docker command.
2. **Get the code** (the repo is public, so no login is needed). Your home folder is fine:
   ```bash
   cd ~
   git clone https://github.com/EamenFarand/daytrip_website.git trapvrij
   cd trapvrij/lifts
   ```
3. **Fill in the settings:**
   ```bash
   cp .env.example .env
   nano .env
   ```
   Fill in the three lines, with no spaces around the `=`:
   - `CF_ACCOUNT_ID`: the same Account ID you put in GitHub. Cloudflare also shows it on *Workers & Pages* (right-hand side) and in the dashboard's web address.
   - `CF_KV_NAMESPACE_ID`: the store's ID from part A.1.
   - `CF_API_TOKEN`: the token from part A.2.

   Save with Ctrl+O and Enter, then close with Ctrl+X. Then, so only you can read the file:
   ```bash
   chmod 600 .env
   ```
4. **Start it:**
   ```bash
   docker compose up -d --build
   ```
   The first time takes a minute or two, while it builds the image.
5. **Watch it work:**
   ```bash
   docker compose logs -f
   ```
   Ctrl+C stops watching; the listener keeps running. You should see:
   - `connected to tcp://pubsub.besteffort.ndovloket.nl:7666`;
   - then, every few minutes until about 04:02 the next night, `not publishing: no full state yet`. That's expected: it waits for the nightly full status.
6. **The next morning,** run `docker compose logs --tail 20` (in `~/trapvrij/lifts`). You should see `full state: … lifts` and then `published: … of … lifts out` about every 10 minutes. Tell me, and I'll check the site.

It restarts by itself after a crash or a reboot, as long as Docker itself starts at boot. That's the default on most systems; if not, `sudo systemctl enable docker`. To update later: `cd ~/trapvrij && git pull && cd lifts && docker compose up -d --build`.

### 2. Optional: send NDOV Loket two questions

Even an always-on listener can't fix a silent feed. On 2 October no lift changes arrived from 00:55 until at least 20:28, while the feed's heartbeats and the 04:02 full state kept coming. If you want, send this (contact details on <https://ndovloket.nl>):

> **Onderwerp:** SIRI-FM liftstatus: stilte op 2 oktober, en de actuele stand ophalen
>
> Beste NDOV Loket,
>
> Voor Trapvrij (trapvrij.nl), een gratis kaart die laat zien welke treinstations je zonder trappen kunt bereiken, tonen we liftstoringen uit de SIRI-FM-berichten van DOVA (`/DOVA/ServiceDelivery` op `pubsub.besteffort.ndovloket.nl`).
>
> 1. Op 2 oktober kwamen er vanaf 00:55 geen statuswijzigingen meer binnen; om 20:30 nog steeds niet. De heartbeats en de volledige stand van 04:02 kwamen wel door. Is dat bekend? Kunnen we zo'n verstoring ergens zien?
> 2. Is er naast de ZeroMQ-stroom een manier om de actuele stand van alle liften op te halen, bijvoorbeeld een bestand of endpoint dat regelmatig wordt ververst? Dan kunnen we bij zo'n stilte terugvallen op een actuele stand.
>
> Met vriendelijke groet,
> Daan

### 3. Optional: desk check of 3 doubtful stations

The data calls these step-free, but another source says no and nothing in the lift/ramp register supports "yes". Until checked, they are **unknown** (not step-free), so doing nothing is safe. If you ever pass one, a look would settle it:

- **Eindhoven Strijp-S**: are both platforms reachable without stairs?
- **Rotterdam Stadion**: event-only station; is there a step-free route?
- **Diemen Zuid**: is the lift to the train platform in service (the register says "project")?

### 4. NS API key: waiting for NS's approval *(not blocking)*

You requested the travel information API ("Reisinformatie API"); that's the right one. It's only needed for an extra accuracy check, so nothing waits on it. When approved:

1. Copy the **Primary key** from your profile on <https://apiportal.ns.nl/>.
2. Open the file `.env` in the project folder. It already exists; I created it for the cache settings.
3. Replace the line `# NS_API_KEY=   <- add your ...` with `NS_API_KEY=<your key>`, with no `#` in front.
4. Tell me it's there. **Don't paste the key in chat.** I'll then run the comparison of ~20 routes against the NS journey planner.

### 5. Decide (optional): report data errors to DOVA?

Anomalies found so far:
- Blerick: two tracks on one island platform disagree.
- Den Haag C 11–12 and Groningen 2–3: no status in the data (you confirmed they're step-free).
- Eindhoven Strijp-S and Rotterdam Stadion: doubtful.
- Delft Campus and Santpoort Noord: platforms numbered differently from the timetable.

Reporting them helps everyone who uses this data (the NS app, 9292…). If you want that, I'll draft a short email for you to send.

### 6. Housekeeping

- **Stop Nextcloud from syncing generated folders** (corrected, per the plan). About 330 MB in total:
  - `web/node_modules`: 115 MB;
  - `pipeline/.venv` and `audit/.venv`: 214 MB;
  - `.git`.

  All of these can be rebuilt with one command.
  1. In the Nextcloud desktop client: *Settings → Edit Ignored Files*.
  2. Add three lines: `.git`, `node_modules` and `.venv`. Each pattern matches that folder name anywhere.
  3. Copies already on the Nextcloud server stay there. Delete them on the server (web interface) only if you need the space, and only once the client shows the folders as ignored. Otherwise the deletion could sync back to your PC.
- **If GitHub emails that "Build and deploy" was disabled:** GitHub pauses scheduled workflows in a public repo after 60 days without new commits. To restart it, open the repo's *Actions* tab, choose *Build and deploy*, and click *Enable workflow*. Until then the site keeps working, but with the data from the last build.
- **The GitHub repo is public**, and commit author emails are visible. Fine as is; if you'd rather use GitHub's no-reply address, send it to me and I'll switch.

---

## Answered

- **2026-09-29, Phase 0 go/no-go:** Go.
- **2026-09-29, what counts as a sprinter:** option A, NS Sprinters plus every regional train. Reason: *any train taken must avoid steps inside the train*; IC trains have steps. Logged in DECISIONS.md.
- **2026-09-29, Houten and Houten Castellum in person:** both *accessible pain-free with a pram*. Recorded in `pipeline/overrides/stations.csv` as verified.
- **2026-09-29, NS API:** requested the Reisinformatie API; waiting for approval (item 4). Not crucial: continue without it.
- **2026-09-29, Phase 1 review:** go; Phase 2 (the map frontend) next.
- **2026-09-29, Den Haag Centraal and Groningen:** *all tracks are accessible* (Daan knows both stations). Recorded as corrections (tracks 11–12 and 2–3 had no status in EPIAP).
- **2026-09-30, Utrecht C: fewer stations with a change allowed:** a bug, fixed. More options now never make a journey look worse (DECISIONS.md).
- **2026-10-01, Phase 2 review:** done. Phase 3 expanded in PLAN.md: live lift status, station pages, housekeeping.
- **2026-10-02, name:** **Trapvrij**. It's on the site; the working title is gone.
- **2026-10-02, domain:** `trapvrij.nl`, registered at TransIP. Checked in the .nl registry: active since 2 Oct 14:04 UTC, TransIP nameservers, DNSSEC on. Nameservers moved to Cloudflare the same evening.
- **2026-10-02, error reports:** to deonw_W@hotmail.com. It's on the about page and behind a "Meld het" link in every station panel, with the station in the subject.
  - The address is now public, so expect some spam. An alias can replace it any time; it's set in one place, `web/src/contact.ts`.
- **2026-10-02, Cloudflare:** both GitHub secrets are set.
  - Checked with the workflow *Check Cloudflare secrets*: the token is an active user token, and it may manage Pages in the account (0 projects so far).
  - Re-run that workflow from the Actions tab whenever you replace the token.
- **2026-10-02, live lift status:** option (b), a listener in Docker on Daan's home server (Linux, always on). A second Cloudflare key and the small Cloudflare function are fine. Logged in DECISIONS.md; PLAN.md and CLAUDE.md updated. Setup steps: item 1.
- **2026-10-03, trapvrij.nl connected:** Daan added the domain to the Pages project and a www-to-root redirect. Checked: https://trapvrij.nl serves the site, and www and http redirect to it. The deploy now checks trapvrij.nl.
- **2026-10-03, DNSSEC:** on again. Daan entered Cloudflare's key at TransIP; the registry accepted it at 11:52 and published it at 12:21 (Dutch time). Checked from outside: the DS record on all .nl servers matches Cloudflare's signing key (key tag 2371, algorithm 13), and Google's and Cloudflare's resolvers validate trapvrij.nl and www.
  - **If you ever move the domain away from Cloudflare, or turn DNSSEC off there:** first remove the key at TransIP (*Beheer → DNSSEC-instellingen*), wait a day, and only then make the change. The other way round, the site is unreachable for a large share of visitors until the registry catches up.
- **2026-10-02, Phase 3:** go (after the softer dark mode).
- **2026-10-02, lift logger:** stopped after 71 hours with all three nightly snapshots, and analysed (audit/REPORT.md Q5). The log moved out of Nextcloud to the cache folder.
