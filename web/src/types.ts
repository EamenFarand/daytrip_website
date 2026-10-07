// Shapes of the files the pipeline builds (see pipeline/README.md).

export type Access = "yes" | "partial" | "no" | "unknown";
export type TrackAccess = "yes" | "no" | "unknown";
export type Day = "weekday" | "saturday";
export type Profile = "any" | "stroller";
export type TrainSet = "all" | "sprinter";

export interface Lift {
  id: string; // matches the live lift feed, e.g. "8400340_001"
  code: string | null; // "HTN-LIF-001"
  tracks: string[];
}

export interface Station {
  code: string;
  name: string;
  slug: string; // its page: /station/<slug>/
  aliases: string[];
  trains: number; // train stops per weekday, used to rank search results and labels
  lat: number;
  lon: number;
  status: Access;
  tracks: Record<string, TrackAccess>;
  source: string;
  source_date: string | null;
  verified: string | null;
  notes: string[];
  uic: string | null;
  lifts: Lift[];
}

export interface Meta {
  v: number;
  built: string;
  days: Record<Day, string>;
  window: [number, number];
  max_changes: number;
  stroller_buffer_min: number;
  epiap_date: string;
  gtfs: { version: string; valid: [string, string] };
  sources: { name: string; by: string; url: string; licence?: string }[];
}

/** [median, fastest, departures per hour, changes, "VIA|VIA" ("" if direct), "TRACKS", 1?]
 * TRACKS: departure, then arrival and departure at each change, then arrival; "?" = unknown.
 * The final 1: the journey takes an intercity that counts as without steps because NS marks it accessible
 * (usually the ICNG; DECISIONS 2026-10-07). Older builds (and hand-made tests) may stop after changes or via. */
export type Entry =
  | [number, number, number, number]
  | [number, number, number, number, string]
  | [number, number, number, number, string, string]
  | [number, number, number, number, string, string, 1];

export type Results = Record<Day, Record<Profile, Record<TrainSet, Record<string, (Entry | null)[]>>>>;

export interface OriginDoc {
  v: number;
  origin: string;
  built: string;
  results: Partial<Results>;
}

/** GET /api/lifts, written by the home-server listener (lifts/listener.py). */
export interface LiftStatus {
  v: number;
  updated: string; // when the listener published this
  full_state_at: string | null; // the last nightly full status (~04:02)
  last_message_at: string | null; // the last status message of any kind
  lifts: number;
  out: { id: string; status: string; since: string | null; until: string | null }[]; // status "back": working again < 30 min
}
