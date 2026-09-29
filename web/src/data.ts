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

/** Current lift outages. Optional: the file arrives with the live feed in Phase 3. */
export async function loadLifts(): Promise<LiftStatus | null> {
  try {
    return await getJson<LiftStatus>("lifts.json");
  } catch {
    return null;
  }
}
