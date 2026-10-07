# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

The site is live at **<https://trapvrij.nl>**, with DNSSEC and the live lift status. Nothing from you is open for v1. Item 1 is a decision on a new feature; the rest are optional or waiting on others.

### 1. Decide: trains without steps from NS's own data (ICNG intercities)

You asked on 7 Oct whether intercities that run as ICNG (no steps) can count as trains without steps.
- **The timetables don't say which train type runs a trip** (neither the GTFS feed nor NS's IFF).
- **The type varies per train, even on one route.** On IC 700 (Schiphol–Groningen), one train was an ICNG and the next an ICM, which has steps.

**NS's own journey messages do say it.** They come as InfoPlus via NDOV Loket: open data (CC0), from the same provider as the lift status. They give every train unit NS's flag "toegankelijk" (J/N). In a 3-minute sample on 7 Oct:
- **J (accessible):**
  - all Sprinters (SLT, SNG, Flirt) and most regional trains;
  - the ICNG on IC 500, IC 1100 and Intercity direct.
- **N (not accessible):**
  - VIRM, ICM and DDZ;
  - the ICNG that runs to Brussels;
  - some regional trains the site now counts as step-free: Arriva Zutphen–Oldenzaal and Almelo–Hardenberg (LINT), one Emmen–Zwolle train, and NMBS Roosendaal–Antwerpen.

**Proposal:**
1. **The listener records it.** The lift listener also follows these messages: one extra connection, which is within fair use. It keeps four weeks of which train number ran with all units accessible, per day.
2. **The build only trusts what's consistent.**
   - A train counts as "without steps" only when NS marked all its units accessible on every day it was seen.
   - An intercity needs at least 3 such days of the same day type (weekday or Saturday).
   - A train seen even once with a unit marked N doesn't count.
   - Without the data, the build works as today.
3. **The site says so.**
   - The option becomes "Treinen zonder trapjes": sprinters, stopping trains and intercities that run as ICNG.
   - A journey that uses such an intercity says so, with a note that NS sometimes runs another train.
4. **You update the listener on the server**, with the same steps as last time.
   - After 1–2 weeks of data, the ICNG trains appear.
   - More appear automatically as NS adds ICNGs.

**Your call:** go or not.

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

### 6. Good to know

- **Old copies on the Nextcloud server:** the generated folders that synced before (about 330 MB) are still there. Delete them in the web interface only if you need the space. The client now ignores them, so the deletion won't reach your PC.
- **If GitHub emails that "Build and deploy" failed:** the site keeps working with the last good data; a failed run publishes nothing. One failure can be a hiccup (a source briefly down). If it keeps failing, tell me and I'll look. That happened on 6–7 Oct: works at Wolfheze fell on the days the build had picked (fixed, DECISIONS 2026-10-07).
- **If GitHub emails that "Build and deploy" was disabled:** GitHub pauses scheduled workflows in a public repo after 60 days without new commits. To restart it, open the repo's *Actions* tab, choose *Build and deploy*, and click *Enable workflow*. Until then the site keeps working, but with the data from the last build.

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
- **2026-10-02, error reports:** to Daan's own address at first, replaced on 3 Oct (below). The address is on the about page and behind a "Meld het" link in every station panel, with the station in the subject. It's set in one place, `web/src/contact.ts`.
- **2026-10-02, Cloudflare:** both GitHub secrets are set.
  - Checked with the workflow *Check Cloudflare secrets*: the token is an active user token, and it may manage Pages in the account (0 projects so far).
  - Re-run that workflow from the Actions tab whenever you replace the token.
- **2026-10-02, live lift status:** option (b), a listener in Docker on Daan's home server (Linux, always on). A second Cloudflare key and the small Cloudflare function are fine. Logged in DECISIONS.md; PLAN.md and CLAUDE.md updated. Setup steps: `lifts/README.md`.
- **2026-10-03, trapvrij.nl connected:** Daan added the domain to the Pages project and a www-to-root redirect. Checked: https://trapvrij.nl serves the site, and www and http redirect to it. The deploy now checks trapvrij.nl.
- **2026-10-03, DNSSEC:** on again. Daan entered Cloudflare's key at TransIP; the registry accepted it at 11:52 and published it at 12:21 (Dutch time). Checked from outside: the DS record on all .nl servers matches Cloudflare's signing key (key tag 2371, algorithm 13), and Google's and Cloudflare's resolvers validate trapvrij.nl and www.
  - **If you ever move the domain away from Cloudflare, or turn DNSSEC off there:** first remove the key at TransIP (*Beheer → DNSSEC-instellingen*), wait a day, and only then make the change. The other way round, the site is unreachable for a large share of visitors until the registry catches up.
- **2026-10-03, report address:** `meld@trapvrij.nl`, which Cloudflare Email Routing forwards to Daan's own mailbox. Daan tested it; the MX and SPF records are live. The site uses it since 3 Oct, and Daan's personal address is gone from the site and the docs. Older versions in the git history still contain it; we leave the history as is.
- **2026-10-03, commit email:** new commits in this repo use Daan's GitHub no-reply address, `196313083+EamenFarand@users.noreply.github.com`, set in the repo's own git settings (`.git/config`). Older commits keep the old address.
- **2026-10-03, GitHub email privacy:** Daan turned on *Keep my email addresses private* and *Block command line pushes that expose my email* (GitHub, *Settings → Emails*). A push with his private address in a new commit is now refused.
- **2026-10-03, Google Search Console:** the domain property is verified (DNS TXT record), and Daan submitted the sitemap. Check indexing around 17 Oct (PLAN.md, housekeeping).
- **2026-10-03, Bing:** Daan imported the site from Search Console into Bing Webmaster Tools, which also covers DuckDuckGo and Ecosia.
- **2026-10-03, Nextcloud:** `.git`, `node_modules`, `.venv` and `.env` are on the client's ignore list (checked in its `sync-exclude.lst`), so the generated folders and the local settings file no longer sync.
- **2026-10-04, lift listener:** runs on Daan's server since 3 Oct (setup and commands: `lifts/README.md`). The full status arrived on 4 Oct at 04:02, and since then it publishes every few minutes, e.g. 50 of 443 lifts out. Checked on the live site: `/api/lifts` serves it, station panels list the lifts that are out with the time of the status, and 10 of Houten's destinations show a warning.
- **2026-10-04, lifts that flip:** option A. A lift that has just come back keeps a softer warning for 30 minutes ("sinds 21:43 weer in gebruik, maar was net nog buiten gebruik"). DECISIONS.md, 2026-10-04.
- **2026-10-04, listener updated:** at 20:10 UTC, carrying on from its saved state. The first lift just back was UT-LIF-009 (Utrecht Centraal, tracks 14/15) at 22:10 Dutch time. Two minutes later the site showed it as "net weer in gebruik": on Houten → Utrecht Zuilen, which changes there, and in the Utrecht Centraal panel.
- **2026-10-02, Phase 3:** go (after the softer dark mode).
- **2026-10-02, lift logger:** stopped after 71 hours with all three nightly snapshots, and analysed (audit/REPORT.md Q5). The log moved out of Nextcloud to the cache folder.
