// Station search that forgives typos and common abbreviations ("Utrecht CS", "A'dam", "Den Bosch").

import type { Station } from "./types";

/** Colloquial names that share no words with the official one. */
const COLLOQUIAL: Record<string, string[]> = {
  HT: ["den bosch", "bosch"],
  ASB: ["bijlmer", "arena"],
  SHL: ["schiphol"],
  GVC: ["den haag cs", "haag centraal"],
  EHS: ["beukenlaan"],
};

/** Word-level shorthand, applied to both the query and the station names ("a/d" = "aan de").
 * Also the English words visitors type: "Amsterdam Central Station", "The Hague". */
const SHORTHAND: Record<string, string> = {
  cs: "centraal",
  ctr: "centraal",
  central: "centraal",
  station: "",
  the: "de",
  hague: "haag",
  adam: "amsterdam",
  rdam: "rotterdam",
  dh: "de haag",
  den: "de",
  v: "van",
  a: "aan",
  d: "de",
  s: "", // 's-Hertogenbosch
};

export function normalise(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "") // accents: Liège -> liege
    .replace(/['’`´]/g, "") // A'dam -> adam, 's-Hertogenbosch -> s-hertogenbosch
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Split into words and expand shorthand. In a query, a last word of one letter is
 * still being typed ("a" for Amsterdam), so it isn't expanded. */
function words(text: string, query = false): string[] {
  const raw = normalise(text).split(" ").filter(Boolean);
  return raw
    .flatMap((w, i) => {
      const typing = query && i === raw.length - 1 && w.length === 1;
      return w in SHORTHAND && !typing ? SHORTHAND[w].split(" ") : [w];
    })
    .filter(Boolean);
}

/** Optimal string alignment distance (Damerau-Levenshtein with adjacent swaps), capped. */
export function editDistance(a: string, b: string, cap = 3): number {
  if (Math.abs(a.length - b.length) > cap) return cap + 1;
  const d: number[][] = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost);
      if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
    }
  }
  return d[a.length][b.length];
}

function allowedTypos(word: string): number {
  return word.length <= 3 ? 0 : word.length <= 6 ? 1 : 2;
}

/** How well one query word matches one name word: 3 exact, 2 prefix, 1 close (typo), 0 no. */
function wordScore(q: string, w: string, last: boolean): number {
  if (q === w) return 3;
  if (last && w.startsWith(q)) return 2; // still typing
  if (w.startsWith(q) && q.length >= 4) return 2;
  const typos = allowedTypos(q);
  if (typos === 0) return 0;
  if (editDistance(q, w, typos) <= typos) return 1;
  if (last && w.length > q.length && editDistance(q, w.slice(0, q.length), typos) <= typos) return 1;
  return 0;
}

interface Indexed {
  station: Station;
  names: string[][]; // word lists: official name, aliases, colloquial names
}

export class StationSearch {
  private index: Indexed[];

  constructor(stations: Station[]) {
    this.index = stations.map((station) => ({
      station,
      names: [station.name, ...station.aliases, ...(COLLOQUIAL[station.code] ?? [])].map((n) => words(n)),
    }));
  }

  search(query: string, limit = 8): Station[] {
    const q = words(query, true);
    if (q.length === 0) return [];
    const code = normalise(query).replace(/ /g, "").toUpperCase();
    const scored: { station: Station; score: number }[] = [];
    for (const item of this.index) {
      let best = item.station.code === code ? 1000 : 0;
      for (const name of item.names) best = Math.max(best, scoreName(q, name));
      if (best > 0) scored.push({ station: item.station, score: best });
    }
    scored.sort((a, b) => b.score - a.score || b.station.trains - a.station.trains || a.station.name.localeCompare(b.station.name, "nl"));
    return scored.slice(0, limit).map((s) => s.station);
  }
}

/** Every query word must match a different name word; exact and whole-name matches score highest. */
function scoreName(q: string[], name: string[]): number {
  const used = new Set<number>();
  let total = 0;
  for (let i = 0; i < q.length; i++) {
    let best = 0;
    let at = -1;
    for (let j = 0; j < name.length; j++) {
      if (used.has(j)) continue;
      const s = wordScore(q[i], name[j], i === q.length - 1);
      if (s > best) [best, at] = [s, j];
    }
    if (best === 0) return 0;
    used.add(at);
    total += best;
  }
  const complete = q.length === name.length && total === 3 * q.length;
  const startsRight = used.has(0);
  return total * 100 + (complete ? 500 : 0) + (startsRight ? 50 : 0) - (name.length - q.length) * 10;
}
