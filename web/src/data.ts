// Load the pipeline's output. Paths are absolute so /station/UT pages load the same files.

import type { LiftStatus, Meta, OriginDoc, Station } from "./types";

const BASE = "/data";

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}/${path}`);
  if (!res.ok) throw new Error(`${path}: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const loadMeta = () => getJson<Meta>("meta.json");
export const loadStations = () => getJson<Station[]>("stations.json");

const origins = new Map<string, Promise<OriginDoc>>();

/** Origin files are fetched once per page view and kept (about 10 KB each over the wire). */
export function loadOrigin(code: string): Promise<OriginDoc> {
  let p = origins.get(code);
  if (!p) {
    p = getJson<OriginDoc>(`origins/${encodeURIComponent(code)}.json`);
    p.catch(() => origins.delete(code));
    origins.set(code, p);
  }
  return p;
}

/** Current lift outages, from the home-server listener via a Cloudflare function. None (yet) = unknown. */
export async function loadLifts(): Promise<LiftStatus | null> {
  try {
    const res = await fetch("/api/lifts");
    if (!res.ok) return null;
    const lifts = (await res.json()) as LiftStatus;
    return Array.isArray(lifts.out) ? lifts : null;
  } catch {
    return null;
  }
}
