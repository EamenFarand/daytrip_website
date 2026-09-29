"""Q3 + Q6: OpenStreetMap cross-check via one Overpass query (ODbL).

Pulls every railway station in the Netherlands with its accessibility tags,
plus all elevators in NL (counted within 250 m of each station locally), so we can see how
OSM's picture compares with the official sources.

Output (data/raw/derived/): osm_rail_stations.parquet
"""

from __future__ import annotations

import json
import time

import polars as pl
import requests

from fetch import RAW, USER_AGENT

OVERPASS = "https://overpass-api.de/api/interpreter"
CACHE = RAW / "osm" / "stations.json"
DERIVED = RAW / "derived"
MAX_AGE_S = 7 * 24 * 3600  # OSM changes slowly; don't hammer Overpass

QUERY = """
[out:json][timeout:180];
area["ISO3166-1"="NL"][admin_level=2]->.nl;
(
  nwr["railway"="station"]["train"!="no"]["station"!~"subway|light_rail|miniature"](area.nl);
  nwr["railway"="halt"]["train"!="no"](area.nl);
)->.st;
.st out tags center;
node["highway"="elevator"](area.nl);
out;
"""


def load() -> dict:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if CACHE.exists() and time.time() - CACHE.stat().st_mtime < MAX_AGE_S:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    r = requests.post(OVERPASS, data={"data": QUERY}, headers={"User-Agent": USER_AGENT}, timeout=300)
    r.raise_for_status()
    CACHE.write_text(r.text, encoding="utf-8")
    return r.json()


def main() -> None:
    data = load()
    stations, elevators = [], []
    for el in data["elements"]:
        t = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        if t.get("railway") in ("station", "halt"):
            stations.append(
                {
                    "osm_id": f"{el['type']}/{el['id']}",
                    "osm_name": t.get("name"),
                    "osm_ns_code": (t.get("railway:ref") or t.get("ref:crs") or "").upper() or None,
                    "osm_uic": t.get("uic_ref"),
                    "osm_wheelchair": t.get("wheelchair"),
                    "osm_operator": t.get("operator"),
                    "osm_lat": lat,
                    "osm_lon": lon,
                }
            )
        elif t.get("highway") == "elevator":
            elevators.append({"lat": lat, "lon": lon, "wheelchair": t.get("wheelchair")})
    st = pl.DataFrame(stations)
    # count elevators within ~250 m of each station (equirectangular approximation is fine at this scale)
    counts = []
    for row in st.iter_rows(named=True):
        n = sum(
            1
            for e in elevators
            if ((e["lat"] - row["osm_lat"]) * 111_320) ** 2 + ((e["lon"] - row["osm_lon"]) * 68_000) ** 2 < 250**2
        )
        counts.append(n)
    st = st.with_columns(pl.Series("osm_elevators_250m", counts))
    DERIVED.mkdir(parents=True, exist_ok=True)
    st.write_parquet(DERIVED / "osm_rail_stations.parquet")
    print(f"OSM: {st.height} station objects, {len(elevators)} elevator nodes in NL")


if __name__ == "__main__":
    main()
