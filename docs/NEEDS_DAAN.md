# Needs Daan

Everything that needs you, batched. Open items first; answered items are kept at the bottom as a record.

---

## Open

### 1. Review Phase 1, then go / no-go for Phase 2 *(blocks Phase 2)*

The router and precompute are done; see [STATUS.md](STATUS.md) and [pipeline/README.md](../pipeline/README.md).
The questions for you:

- **Results.** Does what's in the summary match your own trips? For example:
  - Houten Castellum → Utrecht C: 13 min, 4× an hour, direct.
  - Utrecht → Amsterdam C with a pram on Sprinters only: 42 min direct but only until 09:38, otherwise 54 min with a change.
- **Journey rules.** I compare journeys *within* 08:30–12:00, and "typical" means the median of the sensible journeys. See DECISIONS.md.

Reply "go" for Phase 2 (map frontend), or tell me what to change.

### 2. Optional: desk check of 3 doubtful stations

The data calls these step-free, but another source says no and nothing in the lift/ramp register supports "yes". Until checked, they are **unknown** (not step-free), so doing nothing is safe. If you ever pass one, a look would settle it:

- **Eindhoven Strijp-S**: are both platforms reachable without stairs?
- **Rotterdam Stadion**: event-only station; is there a step-free route?
- **Diemen Zuid**: is the lift to the train platform in service (the register says "project")?

### 3. NS API key: waiting for NS's approval *(not blocking)*

You requested the travel information API ("Reisinformatie API"); that's the right one. It's only needed for an extra accuracy check, so nothing waits on it. When approved:

1. Copy the **Primary key** from your profile on <https://apiportal.ns.nl/>.
2. Open the file `.env` in the project folder. It already exists; I created it for the cache settings.
3. Replace the line `# NS_API_KEY=   <- add your ...` with `NS_API_KEY=<your key>`, with no `#` in front.
4. Tell me it's there. **Don't paste the key in chat.** I'll then run the comparison of ~20 routes against the NS journey planner.

### 4. Decide (optional): report data errors to DOVA?

Anomalies found so far:
- Blerick: two tracks on one island platform disagree.
- Den Haag C 11–12 and Groningen 2–3: no status in the data (you confirmed they're step-free).
- Eindhoven Strijp-S and Rotterdam Stadion: doubtful.
- Delft Campus and Santpoort Noord: platforms numbered differently from the timetable.

Reporting them helps everyone who uses this data (the NS app, 9292…). If you want that, I'll draft a short email for you to send.

### 5. Housekeeping

- **Stop Nextcloud from syncing `.git`.** In the Nextcloud desktop client: *Settings → Edit Ignored Files*, then add `.git`. Downloads and build output now live outside Nextcloud (`AppData\Local\stepfree-nl`), so only the code syncs.
- **The GitHub repo is public**, and commit author emails are visible. Fine as is; if you'd rather use GitHub's no-reply address, send it to me and I'll switch.
- **The lift-status logger** runs on your PC until about **2 Oct 21:12**. It just stops if the PC sleeps or restarts, no harm done.

---

## Answered

- **2026-09-29, Phase 0 go/no-go:** Go.
- **2026-09-29, what counts as a sprinter:** option A, NS Sprinters plus every regional train. Reason: *any train taken must avoid steps inside the train*; IC trains have steps. Logged in DECISIONS.md.
- **2026-09-29, Houten and Houten Castellum in person:** both *accessible pain-free with a pram*. Recorded in `pipeline/overrides/stations.csv` as verified.
- **2026-09-29, NS API:** requested the Reisinformatie API; waiting for approval (item 3). Not crucial: continue without it.
- **2026-09-29, Den Haag Centraal and Groningen:** *all tracks are accessible* (Daan knows both stations). Recorded as corrections (tracks 11–12 and 2–3 had no status in EPIAP).
