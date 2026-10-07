// Turn the origin file plus the chosen filters into one verdict per station.

import { MAX_MINUTES, type State } from "./state";
import type { Entry, OriginDoc, Station } from "./types";

export type Category =
  | "idle" // no results to judge by yet: no origin, still loading, or an origin a pram can't use
  | "origin"
  | "reachable" // a journey within the filters
  | "out-of-reach" // no journey within the filters (too long, too many changes, or none at all)
  | "not-step-free" // stroller profile: station has no step-free access
  | "unknown-access"; // stroller profile: accessibility not known, so not step-free

export interface Verdict {
  station: Station;
  category: Category;
  entry: Entry | null; // the journey summary, when reachable
  band: number; // 0..4 travel-time band, -1 when not reachable
}

export const BANDS = [30, 60, 90, 120, Infinity]; // labels: list.ts

export function band(minutes: number): number {
  return BANDS.findIndex((limit) => minutes <= limit);
}

/** The entry for "at most k changes": trailing repeats are dropped in the file. */
export function level(entries: (Entry | null)[] | undefined, k: number): Entry | null {
  if (!entries || entries.length === 0) return null;
  return entries[Math.min(k, entries.length - 1)];
}

export function verdicts(stations: Station[], doc: OriginDoc | null, s: State): Verdict[] {
  const dests = doc?.results[s.day]?.[s.profile]?.[s.trains] ?? {};
  return stations.map((station) => {
    if (station.code === s.origin) return { station, category: "origin", entry: null, band: -1 };
    if (s.profile === "stroller" && (station.status === "no" || station.status === "unknown")) {
      return { station, category: station.status === "no" ? "not-step-free" : "unknown-access", entry: null, band: -1 };
    }
    if (!s.origin || !doc) return { station, category: "idle", entry: null, band: -1 };
    const entry = level(dests[station.code], s.maxChanges);
    const fits = entry !== null && (s.maxMinutes >= MAX_MINUTES || entry[0] <= s.maxMinutes);
    if (!fits) return { station, category: "out-of-reach", entry: null, band: -1 };
    return { station, category: "reachable", entry, band: band(entry[0]) };
  });
}

/** Can the chosen origin be used at all with this profile? */
export function originUsable(origin: Station | undefined, s: State): boolean {
  return !!origin && (s.profile === "any" || origin.status === "yes" || origin.status === "partial");
}
