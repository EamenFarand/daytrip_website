# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

### 1. Review the site (Phase 2), then go / no-go for Phase 3 *(blocks Phase 3)*

The map frontend is done; see [STATUS.md](STATUS.md) and [web/README.md](../web/README.md). Two ways to look at it:

- **On your PC:** it's open in the Claude app's browser pane. Or run `npm --prefix web run dev` in the project folder and open <http://localhost:5173>.
- **On your phone** (same Wi-Fi as the PC):
  1. Run `npm --prefix web run dev -- --host` in the project folder.
  2. Open the "Network" address it prints (like `http://192.168.1.23:5173`) on your phone.
  3. If Windows asks whether Node.js may use the network, allow it for private networks only.

What I'd like to know:
- **Your own trips.** Pick Houten Castellum. Do the times, changes and "via" match what you know?
- **Phone use.** Can you work the filters one-handed? Is anything too small, hidden or confusing?
- **Wording.** Is the Dutch clear? In particular: the disclaimer, "Niet bereikbaar binnen je keuzes", and the station panel.
- **Map.** Can you tell the blue shades and the shapes apart?

Reply "go" for Phase 3 (nightly pipeline, live lift warnings, launch), or tell me what to change.

### 2. A name and a domain *(needed to launch in Phase 3)*

The site says "Stepfree NL (werktitel)" for now. Until there's a domain it can run on a free `*.pages.dev` address.

1. Pick a name. It must not use NS or ProRail, or suggest a link with them.
2. Buy the domain at any registrar. Cloudflare sells domains at cost, which makes the setup one step shorter, but it doesn't offer every extension, so check it has the one you want.
3. Tell me the name and where you bought the domain. I'll give you the DNS steps in Phase 3.

### 3. An email address for error reports *(needed for the about page, Phase 3)*

The about page now says a report address is coming. The address will be public on the site, so expect some spam. A separate mailbox or an alias is wise. Tell me which address to show; that's fine to share in chat, since it will be public anyway.

### 4. Cloudflare account and deploy key *(needed early in Phase 3; can wait for your go)*

GitHub Actions will build the site and upload it to Cloudflare Pages. For that it needs a key that can only deploy Pages sites.

1. Create a free account at <https://dash.cloudflare.com/sign-up>.
2. Find your **Account ID**: open *Workers & Pages*; it's shown on the right. It's also the long code in the dashboard's web address.
3. Create the key:
   1. Go to *My Profile → API Tokens → Create Token → Create Custom Token*.
   2. Name it `stepfree-deploy`.
   3. Permission: *Account · Cloudflare Pages · Edit*. Account resources: *Include · your account*.
   4. Click *Continue to summary → Create Token*, and copy the token. It's only shown once.
4. In GitHub, open the repo, then *Settings → Secrets and variables → Actions → New repository secret*. Add two secrets:
   - `CLOUDFLARE_API_TOKEN`: the token;
   - `CLOUDFLARE_ACCOUNT_ID`: the Account ID.
5. Tell me it's done. **Don't paste either value in chat.** If a screen looks different from this, tell me what you see and I'll adjust the steps.

### 5. Optional: desk check of 3 doubtful stations

The data calls these step-free, but another source says no and nothing in the lift/ramp register supports "yes". Until checked, they are **unknown** (not step-free), so doing nothing is safe. If you ever pass one, a look would settle it:

- **Eindhoven Strijp-S**: are both platforms reachable without stairs?
- **Rotterdam Stadion**: event-only station; is there a step-free route?
- **Diemen Zuid**: is the lift to the train platform in service (the register says "project")?

### 6. NS API key: waiting for NS's approval *(not blocking)*

You requested the travel information API ("Reisinformatie API"); that's the right one. It's only needed for an extra accuracy check, so nothing waits on it. When approved:

1. Copy the **Primary key** from your profile on <https://apiportal.ns.nl/>.
2. Open the file `.env` in the project folder. It already exists; I created it for the cache settings.
3. Replace the line `# NS_API_KEY=   <- add your ...` with `NS_API_KEY=<your key>`, with no `#` in front.
4. Tell me it's there. **Don't paste the key in chat.** I'll then run the comparison of ~20 routes against the NS journey planner.

### 7. Decide (optional): report data errors to DOVA?

Anomalies found so far:
- Blerick: two tracks on one island platform disagree.
- Den Haag C 11–12 and Groningen 2–3: no status in the data (you confirmed they're step-free).
- Eindhoven Strijp-S and Rotterdam Stadion: doubtful.
- Delft Campus and Santpoort Noord: platforms numbered differently from the timetable.

Reporting them helps everyone who uses this data (the NS app, 9292…). If you want that, I'll draft a short email for you to send.

### 8. Housekeeping

- **Stop Nextcloud from syncing `.git`.** In the Nextcloud desktop client: *Settings → Edit Ignored Files*, then add `.git`. Downloads and build output now live outside Nextcloud (`AppData\Local\stepfree-nl`), so only the code syncs.
- **The GitHub repo is public**, and commit author emails are visible. Fine as is; if you'd rather use GitHub's no-reply address, send it to me and I'll switch.
- **The lift-status logger** runs on your PC until about **2 Oct 21:12**. It just stops if the PC sleeps or restarts, no harm done.

---

## Answered

- **2026-09-29, Phase 0 go/no-go:** Go.
- **2026-09-29, what counts as a sprinter:** option A, NS Sprinters plus every regional train. Reason: *any train taken must avoid steps inside the train*; IC trains have steps. Logged in DECISIONS.md.
- **2026-09-29, Houten and Houten Castellum in person:** both *accessible pain-free with a pram*. Recorded in `pipeline/overrides/stations.csv` as verified.
- **2026-09-29, NS API:** requested the Reisinformatie API; waiting for approval (item 6). Not crucial: continue without it.
- **2026-09-29, Phase 1 review:** go; Phase 2 (the map frontend) next.
- **2026-09-29, Den Haag Centraal and Groningen:** *all tracks are accessible* (Daan knows both stations). Recorded as corrections (tracks 11–12 and 2–3 had no status in EPIAP).
