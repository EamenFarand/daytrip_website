# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

### 1. Go for Phase 3 *(blocks Phase 3)*

Your Phase 2 review and the setup for launch are done and checked (see "Answered" below). Reply "go" to start Phase 3 as described in [PLAN.md](PLAN.md). Item 2 can be decided at the same time.

### 2. Decide: how the site gets live lift status *(needed in Phase 3)*

The 72-hour lift log is analysed; see [audit/REPORT.md](../audit/REPORT.md), Q5. What matters for this choice:

- **Every night at 04:02 the feed sends the status of all 443 lifts.** It did so on all three nights. About 42 lifts are out of order at any time, and about 14 more have status "unknown".
- **In between, changes arrive 3–6 minutes after they happen**: about 200 real changes a day, for 50–65 lifts.
- **The change stream can go quiet without warning.** On 2 October it stopped at 00:55, and it was still silent at 20:28, more than 19½ hours later. The heartbeats and the 04:02 snapshot kept coming. The feed is officially "best effort".
- **With only the nightly snapshot,** the site would at an average moment miss 3–6 lifts that are out of order, and still warn about 8–10 that already work again.

The options from the plan:

| | How | For | Against |
|---|---|---|---|
| **(a)** | The nightly GitHub job also waits for the 04:02 snapshot and publishes it | Free; nothing to keep running; doesn't depend on the change stream, which can go quiet | Up to a day old: a few outages missed, a few already fixed |
| **(b)** | An always-on listener on your home server publishes changes within minutes | Up to date within minutes, when the feed works | Depends on your server and connection; a key to Cloudflare on that machine; still needs the snapshot because the change stream can stop |
| **(c)** | Ask NDOV Loket for a way to fetch the current state, and about the 2 October silence | Free; with such an endpoint, (a) could refresh every 30 minutes | Depends on their answer |

**My recommendation: (a) for launch, and (c) now.**
- The site will say plainly that it shows lift status as of 04:00, and link to the NS station page for the live status.
- If NDOV Loket offers a way to fetch the current state, the scheduled job refreshes more often.
- (b) only makes sense if the warnings need to be fresher than that, and the 2 October silence shows that even (b) can't guarantee it.

If you agree with (c), send this to NDOV Loket (contact details on <https://ndovloket.nl>):

> **Onderwerp:** SIRI-FM liftstatus: actuele stand ophalen, en stilte op 2 oktober
>
> Beste NDOV Loket,
>
> Voor Trapvrij (trapvrij.nl), een gratis kaart die laat zien welke treinstations je zonder trappen kunt bereiken, willen we liftstoringen tonen uit de SIRI-FM-berichten van DOVA (`/DOVA/ServiceDelivery` op `pubsub.besteffort.ndovloket.nl`).
>
> 1. Is er naast de ZeroMQ-stroom een manier om de actuele stand van alle liften op te halen, bijvoorbeeld een bestand of endpoint dat regelmatig wordt ververst? Wij draaien geen eigen server, dus een periodieke ophaalactie past beter dan een permanente verbinding.
> 2. Op 2 oktober kwamen er vanaf 00:55 geen statuswijzigingen meer binnen; om 20:30 nog steeds niet. De heartbeats en de volledige stand van 04:02 kwamen wel door. Is dat bekend? Kunnen we zo'n verstoring ergens zien?
>
> Met vriendelijke groet,
> Daan

### 3. Point trapvrij.nl at Cloudflare *(any time; needed before launch on the domain)*

The site goes live on a free `*.pages.dev` address first. To serve it on `trapvrij.nl` itself (not only `www.`), Cloudflare must handle the domain's DNS. That's free. The domain stays registered at TransIP.

**Order matters.** DNSSEC is on at TransIP. If you switch nameservers with DNSSEC still on, the domain stops working for most visitors.

1. In Cloudflare: *Add a domain* (or *Add a site*), enter `trapvrij.nl`, and choose the **Free** plan. Keep the records it suggests; the domain is still empty, so it doesn't matter. Cloudflare then shows **two nameservers**, like `abby.ns.cloudflare.com`.
2. At TransIP, open the domain and **turn DNSSEC off**. Save.
3. At TransIP, change the **nameservers** to the two from Cloudflare (TransIP calls this using your own or other nameservers). Save.
4. Wait until Cloudflare says the domain is **active**. That's usually within an hour, sometimes up to a day; Cloudflare emails you.
5. Turn DNSSEC back on, now via Cloudflare:
   1. In Cloudflare, go to *DNS → Settings → DNSSEC → Enable*. Cloudflare shows the key details.
   2. At TransIP, turn DNSSEC on for external nameservers and copy those details over. For .nl, TransIP may ask for the public key (flags 257, algorithm 13) rather than the DS record. If its form is unclear, send me a screenshot of it (no secrets in it).
6. Don't add any records for the site yourself. In Phase 3 I'll connect the domain to the site with the deploy key.

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
- **2026-10-02, domain:** `trapvrij.nl`, registered at TransIP. Checked in the .nl registry: active since 2 Oct 14:04 UTC, TransIP nameservers, DNSSEC on. Next: item 3.
- **2026-10-02, error reports:** to deonw_W@hotmail.com. It's on the about page and behind a "Meld het" link in every station panel, with the station in the subject.
  - The address is now public, so expect some spam. An alias can replace it any time; it's set in one place, `web/src/contact.ts`.
- **2026-10-02, Cloudflare:** both GitHub secrets are set.
  - Checked with the workflow *Check Cloudflare secrets*: the token is an active user token, and it may manage Pages in the account (0 projects so far).
  - Re-run that workflow from the Actions tab whenever you replace the token.
- **2026-10-02, lift logger:** stopped after 71 hours with all three nightly snapshots, and analysed (item 2). The log moved out of Nextcloud to the cache folder.
