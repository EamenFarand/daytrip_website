# Needs Daan

Everything that needs you, batched. Newest on top. Tick items off or delete them when done.

---

## 1. Decide: go / no-go on Phase 0 *(blocks Phase 1)*

Read the verdict at the top of [audit/REPORT.md](../audit/REPORT.md) (a 2-minute read).
My recommendation is **Go**: open data gives a step-free status for 99% of stations, refreshed daily, CC0.
Reply "go", "go, narrowed" or "rethink", plus anything you want changed in the plan.

## 2. Decide: what counts as a "sprinter" for the stroller profile? *(needed early in Phase 1)*

You added to PLAN.md: *"Each route must be possible to ride with a 'sprinter' train, as the stroller is inconvenient with the intercity."* You also added a **sprinter / intercity filter** in Phase 2. I read that as: Phase 1 precomputes both "sprinter only" and "all trains", and the user picks. Correct me if you meant sprinter-only to be fixed for the stroller profile.

Either way I need to know which trains count as "sprinter". The timetable labels trains like this:

| Operator | Labels in the data |
|---|---|
| NS | Sprinter (63 routes), Intercity (39), Intercity direct (4) |
| Arriva, Blauwnet, RRReis, Qbuzz (R-net), Keolis | Stoptrein, Sneltrein, Sprinter, and one "Intercity" (Keolis, Zwolle–Enschede) |
| International | ICE, Eurostar, EuroCity, Nightjet, European Sleeper, GoVolta |

Options:

- **A. (my recommendation)** Allow **NS Sprinter + every regional train** (all Arriva / Keolis / Qbuzz / RRReis / Blauwnet services, whatever their label). These are nearly all low-floor trains with room for a pram. Exclude NS Intercity, Intercity direct and international trains.
- **B.** NS Sprinter and regional *Stoptrein* only (also exclude regional *Sneltrein* and Keolis *Intercity*).
- **C.** Something else. Tell me what bothers you about intercities (the steps into double-deckers? crowding? no room?). It changes the rule. For example, NS's newer single-deck intercities (ICNG) have level boarding, but the timetable doesn't say which train type runs.

Reply with A, B or C (plus the reason if C). Until then I'll build with A as the default and make the rule easy to change.

## 3. In-person check: Houten and Houten Castellum *(before launch, not blocking)*

The data says both are fully step-free, each with **one lift** serving the island platform (tracks 1 and 2). Please check that this is true.

For **each station**:

1. Walk from each street entrance to the platform **without using stairs or escalators**. Note the route: lift, ramp or level.
2. Find the lift and write down the code on its sticker or panel. Expected: `HTN-LIF-001` (Houten) and `HTNC-LIF-001` (Houten Castellum). Does it work?
3. Is there any other lift, ramp or level route we don't know about? (The data has 1 lift and 0 ramps at each.)
4. Ramp steepness, if any: fine with a pram / hard work / too steep.
5. Anything else a parent with a pram would trip over: long detours, a gap or step into the train, narrow gates.
6. Optional: 2–3 photos of the route (lift door with the code, platform).

Put the answers under this item or send them in chat. Quick notes are fine.

## 4. Optional: desk check of 3 doubtful stations

The data calls these step-free, but another source says no and nothing in the lift/ramp register supports "yes". Until checked, they are **unknown** (not step-free), so doing nothing is safe. If you ever pass one, a look would settle it:

- **Eindhoven Strijp-S**: are both platforms reachable without stairs?
- **Rotterdam Stadion**: event-only station; is there a step-free route?
- **Diemen Zuid**: is the lift to the train platform in service (the register says "project")?

## 5. Optional: NS API key *(useful in Phase 1, not needed for accessibility)*

Used to compare our travel times with NS's journey planner for about 20 test pairs.

1. Go to <https://apiportal.ns.nl/> and create an account (free).
2. Go to **Products**, open **Ns-App**, and click **Subscribe**.
3. Open your **Profile** and copy the **Primary key**.
4. In the project folder, create a file named `.env` (git ignores it) containing one line:
   `NS_API_KEY=<paste key here>`
5. Tell me it's there. **Don't paste the key in chat.**

## 6. Decide (optional): report data errors to DOVA?

I found a few anomalies in the official data, for example Blerick, where two tracks on the same island platform disagree. Eindhoven Strijp-S and Rotterdam Stadion are also doubtful. Reporting them helps everyone who uses this data (the NS app, 9292…). If you want that, I'll draft a short email for you to send.

## 7. Housekeeping from setup

- **Stop Nextcloud from syncing `.git`.** In the Nextcloud desktop client: *Settings → Edit Ignored Files*, then add `.git`. Syncing the repository's internal files can corrupt it.
- **The GitHub repo is public**, and commit author emails are visible. Fine as is; if you'd rather use GitHub's no-reply address, send it to me and I'll switch.
- **The lift-status logger** (`audit/lift_listener.py`) runs on your PC until about **2 Oct 21:12**. It just stops if the PC sleeps or restarts, no harm done. Nothing to do.
