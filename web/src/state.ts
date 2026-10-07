// What the visitor has chosen, mirrored in the URL so a view can be shared:
// the origin is the page (/station/houten-castellum/), the rest the hash (#profiel=geen&overstap=2).
// The English pages (/en/station/houten-castellum/) use the same hash, so a view keeps across languages.
// Older links with the origin in the hash (#van=HTNC) still work.
// Nothing is stored anywhere else: no cookies, no local storage.

import { type Lang, PREFIX, lang } from "./i18n";
import type { Day, Profile, TrainSet } from "./types";

export interface State {
  origin: string | null; // station code
  profile: Profile;
  trains: TrainSet;
  day: Day;
  maxChanges: 0 | 1 | 2;
  maxMinutes: number; // MAX_MINUTES = no limit
  selected: string | null; // station shown in the detail panel
}

export const MAX_MINUTES = 240;
export const MINUTE_STEPS = [30, 45, 60, 75, 90, 120, 150, 180, MAX_MINUTES];

export const DEFAULTS: State = {
  origin: null,
  profile: "stroller",
  trains: "sprinter",
  day: "weekday",
  maxChanges: 1,
  maxMinutes: 120,
  selected: null,
};

const PROFILE = { stroller: "kinderwagen", any: "geen" } as const;
const TRAINS = { sprinter: "sprinter", all: "alle" } as const;
const DAY = { weekday: "werkdag", saturday: "zaterdag" } as const;

function reverse<T extends string>(map: Record<T, string>, value: string | null): T | undefined {
  return (Object.keys(map) as T[]).find((k) => map[k] === value);
}

/** Everything except the origin, which is in the path (see pagePath). */
export function toHash(s: State): string {
  const p = new URLSearchParams();
  if (s.profile !== DEFAULTS.profile) p.set("profiel", PROFILE[s.profile]);
  if (s.trains !== DEFAULTS.trains) p.set("treinen", TRAINS[s.trains]);
  if (s.day !== DEFAULTS.day) p.set("dag", DAY[s.day]);
  if (s.maxChanges !== DEFAULTS.maxChanges) p.set("overstap", String(s.maxChanges));
  if (s.maxMinutes !== DEFAULTS.maxMinutes) p.set("max", s.maxMinutes >= MAX_MINUTES ? "alles" : String(s.maxMinutes));
  if (s.selected) p.set("station", s.selected);
  const text = p.toString();
  return text ? `#${text}` : "";
}

export function fromHash(hash: string, known: (code: string) => boolean): State {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const code = (key: string) => {
    const v = p.get(key)?.toUpperCase() ?? null;
    return v && known(v) ? v : null;
  };
  const number = (key: string) => (p.has(key) ? Number(p.get(key)) : NaN); // Number(null) would be 0
  const changes = number("overstap");
  const minutes = p.get("max") === "alles" ? MAX_MINUTES : number("max");
  return {
    origin: code("van"),
    profile: reverse(PROFILE, p.get("profiel")) ?? DEFAULTS.profile,
    trains: reverse(TRAINS, p.get("treinen")) ?? DEFAULTS.trains,
    day: reverse(DAY, p.get("dag")) ?? DEFAULTS.day,
    maxChanges: changes === 0 || changes === 1 || changes === 2 ? changes : DEFAULTS.maxChanges,
    maxMinutes: MINUTE_STEPS.includes(minutes) ? minutes : DEFAULTS.maxMinutes,
    selected: code("station"),
  };
}

/** /station/houten-castellum/ (or /en/station/…) -> "houten-castellum": the station whose page this is. */
export function stationFromPath(path: string): string | null {
  const m = path.match(/^(?:\/en)?\/station\/([a-z0-9]+(?:-[a-z0-9]+)*)\/?$/);
  return m ? m[1] : null;
}

/** The page for an origin, in the page's language: its station page, or the home page. */
export function pagePath(slug: string | null, l: Lang = lang): string {
  return PREFIX[l] + (slug ? `/station/${slug}/` : "/");
}
