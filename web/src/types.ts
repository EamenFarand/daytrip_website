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

/** [median, fastest, departures per hour, changes, "VIA|VIA"?] */
export type Entry = [number, number, number, number] | [number, number, number, number, string];

export type Results = Record<Day, Record<Profile, Record<TrainSet, Record<string, (Entry | null)[]>>>>;

export interface OriginDoc {
  v: number;
  origin: string;
  built: string;
  results: Partial<Results>;
}

/** Optional: filled from the live lift feed in Phase 3. */
export interface LiftStatus {
  updated: string;
  out: { id: string; since: string | null; until: string | null }[];
}
