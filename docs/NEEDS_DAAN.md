# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

The site is live at **<https://trapvrij.nl>**. Items 1 and 2 are what's left from you for v1: DNSSEC and the lift listener.

### 1. Turn DNSSEC back on at TransIP *(Cloudflare's side is done)*

Cloudflare already signs the domain. The .nl registry just doesn't know the key yet, so TransIP has to pass it on. The form isn't on the page in your screenshots; it's behind *Beheer*:

1. In the TransIP control panel: *Domein & Hosting*, then click **trapvrij.nl** in the list on the left. Don't tick its box.
2. Click the **Beheer** (Manage) button next to the domain name, and choose **DNSSEC-instellingen**.
3. Fill in, and check them against Cloudflare (*trapvrij.nl → DNS → Settings → DNSSEC*); I read them from Cloudflare's DNS on 3 Oct:
   - **Key tag:** `2371`
   - **Flags:** `257` (Key Signing Key)
   - **Algoritme:** `13` (ECDSA Curve P-256 with SHA-256)
   - **Public key:** `mdsswUyr3DPW132mOi8V9xESWE8jTo0dxCjjnopKl+GqJxpVXckHAeF+KkxLbxILfDLUT0rAK9iUzy1L53eKGQ==`
4. Click **Opslaan**. It can take a few hours for the registry to publish it. Cloudflare's DNSSEC status then changes from pending to active. Tell me and I'll check from outside.

You can ignore the DNS records on TransIP's domain page (A 37.97.254.27 and so on). Since the nameservers point to Cloudflare, nobody uses them.

### 2. Run the lift listener on your home server

The code is ready: [lifts/README.md](../lifts/README.md). CI checks that its Docker image builds. Until it runs, the site says the lift status is unknown.

1. **Create the store.** In Cloudflare, go to *Storage & Databases → KV → Create* (or find it under *Workers & Pages*). Name it `trapvrij-lifts`, and copy its **ID**.
2. **Create the second key:**
   1. Go to *My Profile → API Tokens → Create Token → Create Custom Token*, and name it `trapvrij-lifts-writer`.
   2. Permission: *Account · Workers KV Storage · Edit*. Account resources: your account.
   3. Click *Continue to summary → Create Token*, and copy the token. It goes only into the env file on your server, never into GitHub or this chat.
3. **Tell me the store's ID.** It isn't secret. I'll connect the store to the site.
4. **On the server:**
   ```bash
   git clone https://github.com/EamenFarand/daytrip_website.git trapvrij
   cd trapvrij/lifts
   cp .env.example .env
   nano .env               # account ID, store ID and the key from step 2
   docker compose up -d --build
   docker compose logs -f  # Ctrl+C stops watching; it keeps running
   ```
   You should see `connected to tcp://pubsub.besteffort.ndovloket.nl:7666`. Until about 04:02 the next night it logs `not publishing: no full state yet`; that's expected. After that it logs `published: … lifts out` about every 10 minutes.

### 3. Optional: send NDOV Loket two questions

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

### 4. Optional: desk check of 3 doubtful stations

The data calls these step-free, but another source says no and nothing in the lift/ramp register supports "yes". Until checked, they are **unknown** (not step-free), so doing nothing is safe. If you ever pass one, a look would settle it:

- **Eindhoven Strijp-S**: are both platforms reachable without stairs?
- **Rotterdam Stadion**: event-only station; is there a step-free route?
- **Diemen Zuid**: is the lift to the train platform in service (the register says "project")?

### 5. NS API key: waiting for NS's approval *(not blocking)*

You requested the travel information API ("Reisinformatie API"); that's the right one. It's only needed for an extra accuracy check, so nothing waits on it. When approved:

1. Copy the **Primary key** from your profile on <https://apiportal.ns.nl/>.
2. Open the file `.env` in the project folder. It already exists; I created it for the cache settings.
3. Replace the line `# NS_API_KEY=   <- add your ...` with `NS_API_KEY=<your key>`, with no `#` in front.
4. Tell me it's there. **Don't paste the key in chat.** I'll then run the comparison of ~20 routes against the NS journey planner.

### 6. Decide (optional): report data errors to DOVA?

Anomalies found so far:
- Blerick: two tracks on one island platform disagree.
- Den Haag C 11–12 and Groningen 2–3: no status in the data (you confirmed they're step-free).
- Eindhoven Strijp-S and Rotterdam Stadion: doubtful.
- Delft Campus and Santpoort Noord: platforms numbered differently from the timetable.

Reporting them helps everyone who uses this data (the NS app, 9292…). If you want that, I'll draft a short email for you to send.

### 7. Housekeeping

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
- **2026-09-29, NS API:** requested the Reisinformatie API; waiting for approval (item 5). Not crucial: continue without it.
- **2026-09-29, Phase 1 review:** go; Phase 2 (the map frontend) next.
- **2026-09-29, Den Haag Centraal and Groningen:** *all tracks are accessible* (Daan knows both stations). Recorded as corrections (tracks 11–12 and 2–3 had no status in EPIAP).
- **2026-09-30, Utrecht C: fewer stations with a change allowed:** a bug, fixed. More options now never make a journey look worse (DECISIONS.md).
- **2026-10-01, Phase 2 review:** done. Phase 3 expanded in PLAN.md: live lift status, station pages, housekeeping.
- **2026-10-02, name:** **Trapvrij**. It's on the site; the working title is gone.
- **2026-10-02, domain:** `trapvrij.nl`, registered at TransIP. Checked in the .nl registry: active since 2 Oct 14:04 UTC, TransIP nameservers, DNSSEC on. Nameservers moved to Cloudflare the same evening (item 2).
- **2026-10-02, error reports:** to deonw_W@hotmail.com. It's on the about page and behind a "Meld het" link in every station panel, with the station in the subject.
  - The address is now public, so expect some spam. An alias can replace it any time; it's set in one place, `web/src/contact.ts`.
- **2026-10-02, Cloudflare:** both GitHub secrets are set.
  - Checked with the workflow *Check Cloudflare secrets*: the token is an active user token, and it may manage Pages in the account (0 projects so far).
  - Re-run that workflow from the Actions tab whenever you replace the token.
- **2026-10-02, live lift status:** option (b), a listener in Docker on Daan's home server (Linux, always on). A second Cloudflare key and the small Cloudflare function are fine. Logged in DECISIONS.md; PLAN.md and CLAUDE.md updated. Setup steps come in Phase 3 (item 3).
- **2026-10-03, trapvrij.nl connected:** Daan added the domain to the Pages project and a www-to-root redirect. Checked: https://trapvrij.nl serves the site, and www and http redirect to it. The deploy now checks trapvrij.nl.
- **2026-10-02, Phase 3:** go (after the softer dark mode).
- **2026-10-02, lift logger:** stopped after 71 hours with all three nightly snapshots, and analysed (audit/REPORT.md Q5). The log moved out of Nextcloud to the cache folder.
