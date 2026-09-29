"""Q1 + Q2: extract the rail network's stations from the OVapi GTFS feed.

Outputs (git-ignored, in data/raw/derived/):
  gtfs_rail_platforms.parquet  one row per platform stop served by a train
  gtfs_rail_stations.parquet   one row per parent station (stoparea)
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import polars as pl

from fetch import RAW, fetch

GTFS_URL = "http://gtfs.ovapi.nl/nl/gtfs-nl.zip"
EXTRACT = RAW / "gtfs-nl"
DERIVED = RAW / "derived"
RAIL_ROUTE_TYPES = ["2"] + [str(t) for t in range(100, 118)]
FILES = ["agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "transfers.txt", "feed_info.txt"]


def extract(zip_path: Path) -> None:
    EXTRACT.mkdir(parents=True, exist_ok=True)
    stamp = EXTRACT / ".source_mtime"
    mtime = str(zip_path.stat().st_mtime)
    if stamp.exists() and stamp.read_text() == mtime:
        return
    with zipfile.ZipFile(zip_path) as z:
        for f in FILES:
            z.extract(f, EXTRACT)
    stamp.write_text(mtime)


def read(name: str) -> pl.LazyFrame:
    return pl.scan_csv(EXTRACT / name, infer_schema=False, encoding="utf8-lossy")


def main() -> None:
    extract(fetch(GTFS_URL, "gtfs-nl.zip"))
    DERIVED.mkdir(parents=True, exist_ok=True)

    agency = read("agency.txt").select("agency_id", "agency_name")
    routes = (
        read("routes.txt")
        .filter(pl.col("route_type").is_in(RAIL_ROUTE_TYPES))
        .join(agency, on="agency_id", how="left")
        .select("route_id", "agency_id", "agency_name")
    )
    trips = read("trips.txt").select("trip_id", "route_id").join(routes, on="route_id")
    served = (
        read("stop_times.txt")
        .select("trip_id", "stop_id")
        .join(trips.select("trip_id", "agency_name"), on="trip_id")
        .group_by("stop_id")
        .agg(
            pl.col("agency_name").unique().sort().str.join("|").alias("operators"),
            pl.col("trip_id").n_unique().alias("n_trips"),
        )
        .collect(engine="streaming")
    )

    stops = read("stops.txt").collect()
    platforms = stops.join(served, on="stop_id").with_columns(
        pl.col("zone_id").str.strip_prefix("IFF:").str.to_uppercase().alias("iff_code")
    )
    platforms.write_parquet(DERIVED / "gtfs_rail_platforms.parquet")

    parents = stops.filter(pl.col("stop_id").is_in(platforms["parent_station"].unique().implode()))
    stations = (
        platforms.group_by("parent_station")
        .agg(
            pl.col("iff_code").drop_nulls().unique().sort().str.join("|").alias("iff_code"),
            pl.col("operators").str.split("|").explode().unique().sort().str.join("|").alias("operators"),
            pl.col("n_trips").sum().alias("n_trips"),
            pl.len().alias("n_platform_stops"),
            pl.col("platform_code").drop_nulls().unique().sort().str.join("|").alias("platform_codes"),
            pl.col("wheelchair_boarding").drop_nulls().unique().sort().str.join("|").alias("wb_platform_values"),
        )
        .join(
            parents.select(
                pl.col("stop_id").alias("parent_station"),
                pl.col("stop_name").alias("gtfs_name"),
                pl.col("stop_lat").cast(pl.Float64).alias("lat"),
                pl.col("stop_lon").cast(pl.Float64).alias("lon"),
                pl.col("wheelchair_boarding").alias("wb_parent"),
                pl.col("location_type").alias("parent_location_type"),
            ),
            on="parent_station",
            how="left",
        )
        .rename({"parent_station": "gtfs_parent_id"})
        .sort("gtfs_name")
    )
    stations.write_parquet(DERIVED / "gtfs_rail_stations.parquet")
    print(f"rail platform stops: {platforms.height}, parent stations: {stations.height}")


if __name__ == "__main__":
    main()
