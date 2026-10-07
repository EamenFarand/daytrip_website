// Live lift status: how fresh it is, and which lifts are out along a journey.
// The data comes from the listener on Daan's home server (lifts/, DECISIONS 2026-10-02).
// Stale data looks like no data: old status is shown as unknown, never as "all lifts work".

import { clock, platformText, upperFirst } from "./format";
import { tr } from "./i18n";
import type { Entry, Lift, LiftStatus, Station } from "./types";

export const SILENT_AFTER_MIN = 30; // two lifts resend every 5 minutes, so 30 quiet minutes = changes stopped
export const STALE_AFTER_H = 26; // the full status comes every night; older than this = unknown

/** live: changes come in; nightly: only the 04:02 full status is reliable; unknown: too old or none */
export type Freshness = "live" | "nightly" | "unknown";

export function freshness(lifts: LiftStatus | null, now: Date): Freshness {
  if (!lifts?.full_state_at) return "unknown";
  const minutes = (iso: string | null) => (iso ? (now.getTime() - Date.parse(iso)) / 60_000 : Infinity);
  if (minutes(lifts.full_state_at) > STALE_AFTER_H * 60) return "unknown";
  // the listener publishes at least every 10 minutes; much older means changes may be missing
  if (minutes(lifts.last_message_at) > SILENT_AFTER_MIN || minutes(lifts.updated) > SILENT_AFTER_MIN) return "nightly";
  return "live";
}

export function freshnessText(lifts: LiftStatus | null, fresh: Freshness): string {
  if (fresh === "live" && lifts) {
    const at = clock(minutesOfDay(lifts.updated));
    return tr({ nl: `Liftstatus van ${at} uur.`, en: `Lift status as of ${at}.` });
  }
  if (fresh === "nightly" && lifts?.full_state_at) {
    const at = clock(minutesOfDay(lifts.full_state_at));
    return tr({
      nl: `Liftstatus van ${at} uur vannacht; storingen van daarna kunnen ontbreken.`,
      en: `Lift status as of ${at} last night; later outages may be missing.`,
    });
  }
  return tr({
    nl: "De actuele liftstatus is nu niet bekend. Controleer de liften vóór vertrek.",
    en: "The current lift status is not known right now. Check the lifts before you travel.",
  });
}

function minutesOfDay(iso: string): number {
  const d = new Date(iso);
  return d.getHours() * 60 + d.getMinutes();
}

export interface OutLift {
  lift: Lift;
  status: string; // notAvailable, unknown, back, ...
  since: string | null;
  until: string | null;
}

/** "back": working again for less than half an hour. The listener keeps such a lift listed,
 * because lifts often fail again soon (DECISIONS 2026-10-04). */
export type Trouble = "out" | "unknown" | "back";

export function trouble(o: { status: string }): Trouble {
  return o.status === "back" ? "back" : o.status === "unknown" ? "unknown" : "out";
}

/** What is wrong with a lift: "buiten gebruik", "status onbekend" or "sinds 21:43 weer in gebruik, …". */
export function statusText(o: { status: string; since: string | null }): string {
  const t = trouble(o);
  if (t === "unknown") return tr({ nl: "status onbekend", en: "status unknown" });
  if (t === "back") {
    const at = o.since ? clock(minutesOfDay(o.since)) : null;
    return tr({
      nl: `${at ? `sinds ${at} ` : ""}weer in gebruik, maar was net nog buiten gebruik`,
      en: `back in service${at ? ` since ${at}` : ""}, but was out of order until just now`,
    });
  }
  return tr({ nl: "buiten gebruik", en: "out of order" });
}

/** Lifts at a station that aren't working, or whose status is unknown. Nothing when the data can't be trusted. */
export function outAt(station: Station, lifts: LiftStatus | null, fresh: Freshness): OutLift[] {
  if (!lifts || fresh === "unknown") return [];
  const out = new Map(lifts.out.map((o) => [o.id, o]));
  return station.lifts.filter((l) => out.has(l.id)).map((l) => ({ lift: l, ...out.get(l.id)! }));
}

const trackNumber = (t: string) => t.toLowerCase().replace(/[a-z]+$/, ""); // sector 18a is on track 18

/** Could this lift be needed at this stop of the journey?
 * A platform lift: if it serves a track used there (or the track isn't known).
 * A lift in the hall or at an entrance: only where you enter or leave the station, not when changing trains. */
export function serves(lift: Lift, tracks: string[], role: Role): boolean {
  if (!lift.tracks.length) return role !== "overstap";
  if (!tracks.length || tracks.includes("?")) return true;
  const used = new Set(tracks.map(trackNumber));
  return lift.tracks.some((t) => used.has(trackNumber(t)));
}

/** Where a lift is: "spoor 14/15", or "hal of ingang" for one that serves no platform. */
export function liftPlace(lift: Lift): string {
  return lift.tracks.length ? platformText(lift.tracks) : tr({ nl: "hal of ingang", en: "hall or entrance" });
}

export function outText(o: OutLift): string {
  return `lift ${o.lift.code ?? o.lift.id} (${liftPlace(o.lift)}): ${statusText(o)}`;
}

export type Role = "vertrek" | "overstap" | "aankomst";

export function roleText(role: Role): string {
  return tr({ vertrek: { nl: "vertrek", en: "departure" }, overstap: { nl: "overstap", en: "change" }, aankomst: { nl: "aankomst", en: "arrival" } }[role]);
}

export interface StationWarning {
  station: Station;
  role: Role;
  out: OutLift[];
}

/** Every station of a journey (origin, each change, destination) with a lift out that the journey may need. */
export function journeyWarnings(
  entry: Entry | null,
  origin: Station | undefined,
  dest: Station,
  byCode: Map<string, Station>,
  lifts: LiftStatus | null,
  fresh: Freshness,
): StationWarning[] {
  if (!entry || !origin) return [];
  const via = entry[4] ? entry[4].split("|") : [];
  const tracks = entry[5]?.split("|") ?? []; // none (older build): every lift at the station counts
  const at = (i: number) => (tracks.length ? [tracks[i]] : []);
  const stops: [Station | undefined, Role, string[]][] = [
    [origin, "vertrek", at(0)],
    ...via.map((c, i): [Station | undefined, Role, string[]] => [byCode.get(c), "overstap", tracks.length ? [tracks[1 + 2 * i], tracks[2 + 2 * i]] : []]),
    [dest, "aankomst", at(tracks.length - 1)],
  ];
  return stops
    .filter((s): s is [Station, Role, string[]] => s[0] !== undefined)
    .map(([station, role, used]) => ({ station, role, out: outAt(station, lifts, fresh).filter((o) => serves(o.lift, used, role)) }))
    .filter((w) => w.out.length > 0);
}

/** "⚠ lift buiten gebruik", "⚠ liftstatus onbekend" or "⚠ lift net weer in gebruik", for a station on the journey. */
export function liftNote(w: StationWarning): string {
  const kinds = new Set(w.out.map(trouble));
  if (kinds.has("out")) return tr({ nl: "⚠ lift buiten gebruik", en: "⚠ lift out of order" });
  if (kinds.has("unknown")) return tr({ nl: "⚠ liftstatus onbekend", en: "⚠ lift status unknown" });
  return tr({ nl: "⚠ lift net weer in gebruik", en: "⚠ lift just back in service" });
}

/** The list's warning line: stations with a lift out of order first, then those where a lift has just come back. */
export function warnLine(warnings: StationWarning[]): string {
  const justBack = (w: StationWarning) => w.out.every((o) => trouble(o) === "back");
  const out = warnings.filter((w) => !justBack(w)).map((w) => w.station.name);
  const back = warnings.filter(justBack).map((w) => w.station.name);
  const parts = [
    out.length ? tr({ nl: `Liftstoring: ${out.join(", ")}`, en: `Lift out of order: ${out.join(", ")}` }) : "",
    back.length ? tr({ nl: `lift net weer in gebruik: ${back.join(", ")}`, en: `lift just back in service: ${back.join(", ")}` }) : "",
  ];
  return `⚠ ${upperFirst(parts.filter(Boolean).join("; "))}`;
}
