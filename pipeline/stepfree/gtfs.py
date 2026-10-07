"""Load the rail part of the OVapi GTFS feed.

- which dates to use (one representative weekday and one Saturday),
- one day's rail timetable at platform level, Dutch stations only,
- NS's trip-specific transfer rules for that day.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from .config import CACHE, EXCLUDED_AGENCIES, GTFS_URL, IFF_URL
from .fetch import fetch

EXTRACT = CACHE / "gtfs-nl"
FILES = ["agency.txt", "routes.txt", "trips.txt", "stops.txt", "stop_times.txt", "transfers.txt",
         "calendar_dates.txt", "feed_info.txt"]
RAIL_ROUTE_TYPES = ["2"] + [str(t) for t in range(100, 118)]


def ensure_feed() -> Path:
    """Download (if changed) and unpack the files we need; returns the unpack folder."""
    zip_path = fetch(GTFS_URL, "gtfs-nl.zip")
    EXTRACT.mkdir(parents=True, exist_ok=True)
    stamp = EXTRACT / ".source_mtime"
    mtime = str(zip_path.stat().st_mtime)
    missing = [f for f in FILES if not (EXTRACT / f).exists()]
    if missing or not stamp.exists() or stamp.read_text() != mtime:
        with zipfile.ZipFile(zip_path) as z:
            for f in FILES:
                z.extract(f, EXTRACT)
        stamp.write_text(mtime)
    return EXTRACT


def _read(name: str) -> pl.LazyFrame:
    return pl.scan_csv(EXTRACT / name, infer_schema=False, encoding="utf8-lossy")


def feed_info() -> dict:
    return _read("feed_info.txt").collect().row(0, named=True)


def iff_stations() -> pl.DataFrame:
    """NS station codes with country and default transfer time (minutes), from the IFF timetable."""
    z = zipfile.ZipFile(fetch(IFF_URL, "ns-latest.zip"))
    rows = []
    for line in z.read("stations.dat").decode("latin1").splitlines()[1:]:
        f = [x.strip() for x in line.split(",")]
        rows.append({"code": f[1].upper(), "country": f[4], "transfer_min": int(f[2]), "iff_name": f[9]})
    return pl.DataFrame(rows)


def rail_trips() -> pl.DataFrame:
    """All rail trips in the feed with operator and category, minus buses and heritage lines."""
    agency = _read("agency.txt").select("agency_id", "agency_name")
    routes = (
        _read("routes.txt")
        .filter(pl.col("route_type").is_in(RAIL_ROUTE_TYPES))
        .join(agency, on="agency_id", how="left")
        .filter(~pl.col("agency_name").is_in(list(EXCLUDED_AGENCIES)))
        .select("route_id", "agency_name")
    )
    return (
        _read("trips.txt")
        .join(routes, on="route_id")
        .select("trip_id", "service_id", "agency_name",
                pl.col("trip_long_name").alias("category"), pl.col("trip_short_name").alias("train_number"))
        .collect()
    )


def service_dates() -> pl.DataFrame:
    return (
        _read("calendar_dates.txt")
        .filter(pl.col("exception_type") == "1")
        .select("service_id", pl.col("date").str.to_date("%Y%m%d"))
        .collect()
    )


def _station_of(nl_codes: set[str]) -> pl.DataFrame:
    """stop_id -> Dutch station code, for the platform stops (zone "IFF:<code>")."""
    return (
        _read("stops.txt").select("stop_id", "zone_id").collect()
        .filter(pl.col("zone_id").str.starts_with("IFF:"))
        .select("stop_id", pl.col("zone_id").str.strip_prefix("IFF:").str.to_uppercase().alias("station"))
        .filter(pl.col("station").is_in(list(nl_codes)))
    )


def station_calls(trips: pl.DataFrame, nl_codes: set[str]) -> pl.DataFrame:
    """Which Dutch stations each rail trip stops at: trip_id, station (stops where you can get on or off)."""
    return (
        _read("stop_times.txt")
        .filter(pl.col("trip_id").is_in(trips["trip_id"].implode())
                & ((pl.col("pickup_type").fill_null("0") != "1") | (pl.col("drop_off_type").fill_null("0") != "1")))
        .select("trip_id", "stop_id")
        .collect(engine="streaming")
        .join(_station_of(nl_codes), on="stop_id")
        .select("trip_id", "station")
        .unique()
    )


def choose_days(calls: pl.DataFrame, trips: pl.DataFrame, dates: pl.DataFrame, today: date,
                horizon_days: int = 56) -> dict[str, date]:
    """Pick the Tue/Wed/Thu and the Saturday with the most normal service in the next eight weeks.

    Engineering works close stations, so first: the most regular stations served. A regular station
    has trains on at least half the days; only those count, which leaves out event-only stops like
    Rotterdam Stadion. Then: the most calls at them. Not the most trips: works split through trains
    into two trips, so on 27-29 Oct 2026 the days with the most trips were the ones with Wolfheze closed.
    Eight weeks, because weekend works are common: no Saturday in the four weeks after 7 Oct 2026 was clean.
    Ties go to the earliest date.
    """
    per_day = (
        calls.join(trips.select("trip_id", "service_id"), on="trip_id")
        .join(dates.filter(pl.col("date").is_between(today + timedelta(days=1), today + timedelta(days=horizon_days))),
              on="service_id")
        .select("date", "station")
    )
    days_served = per_day.unique().group_by("station").len()
    regular = days_served.filter(pl.col("len") * 2 >= per_day["date"].n_unique())["station"]
    score = (
        per_day.filter(pl.col("station").is_in(regular.implode()))
        .group_by("date")
        .agg(pl.col("station").n_unique().alias("stations"), pl.len().alias("calls"))
        .with_columns(pl.col("date").dt.weekday().alias("dow"))  # 1 = Monday
    )
    out = {}
    for name, dows in (("weekday", [2, 3, 4]), ("saturday", [6])):
        c = score.filter(pl.col("dow").is_in(dows)).sort(["stations", "calls", "date"], descending=[True, True, False])
        if c.is_empty():
            raise RuntimeError(f"no {name} in the feed within {horizon_days} days of {today}")
        out[name] = c["date"][0]
    return out


def _minutes(col: str) -> pl.Expr:
    parts = pl.col(col).str.split(":")
    return parts.list.get(0).cast(pl.Int32) * 60 + parts.list.get(1).cast(pl.Int32)


@dataclass
class DayTimetable:
    day: date
    trips: pl.DataFrame  # trip_id, agency_name, category, train_number
    stop_times: pl.DataFrame  # trip_id, seq, station, platform, arr, dep, can_board, can_alight
    stations: pl.DataFrame  # code, name, lat, lon (Dutch stations served this day)
    transfers: pl.DataFrame  # from_trip, to_trip, station, from_platform, to_platform, kind


def day_timetable(day: date, trips: pl.DataFrame, dates: pl.DataFrame, nl_codes: set[str]) -> DayTimetable:
    """Rail stop events for one day at Dutch stations, at platform level, times in minutes."""
    active = trips.join(dates.filter(pl.col("date") == day), on="service_id").drop("service_id", "date")
    stops = _read("stops.txt").select("stop_id", "stop_name", "stop_lat", "stop_lon", "parent_station",
                                      "platform_code", "zone_id").collect()
    platforms = (
        stops.filter(pl.col("zone_id").str.starts_with("IFF:"))
        .with_columns(pl.col("zone_id").str.strip_prefix("IFF:").str.to_uppercase().alias("station"))
        .filter(pl.col("station").is_in(list(nl_codes)))
        .select("stop_id", "station", pl.col("platform_code").fill_null("?").alias("platform"), "parent_station")
    )
    st = (
        _read("stop_times.txt")
        .filter(pl.col("trip_id").is_in(active["trip_id"].implode()))
        .select("trip_id", "stop_sequence", "stop_id", "arrival_time", "departure_time", "pickup_type", "drop_off_type")
        .collect(engine="streaming")
        .join(platforms.select("stop_id", "station", "platform"), on="stop_id")
        .select(
            "trip_id",
            pl.col("stop_sequence").cast(pl.Int32).alias("seq"),
            "station",
            "platform",
            _minutes("arrival_time").alias("arr"),
            _minutes("departure_time").alias("dep"),
            (pl.col("pickup_type").fill_null("0") != "1").alias("can_board"),
            (pl.col("drop_off_type").fill_null("0") != "1").alias("can_alight"),
        )
        .sort("trip_id", "seq")
    )
    parents = stops.filter(pl.col("stop_id").is_in(platforms["parent_station"].unique().implode()))
    stations = (
        platforms.filter(pl.col("station").is_in(st["station"].unique().implode()))
        .group_by("station")
        .agg(pl.col("parent_station").first())
        .join(parents.select(pl.col("stop_id").alias("parent_station"), "stop_name",
                             pl.col("stop_lat").cast(pl.Float64), pl.col("stop_lon").cast(pl.Float64)),
              on="parent_station", how="left")
        .select(pl.col("station").alias("code"), pl.col("stop_name").alias("name"),
                pl.col("stop_lat").alias("lat"), pl.col("stop_lon").alias("lon"))
        .sort("code")
    )
    kinds = {"0": "possible", "1": "guaranteed", "3": "impossible"}
    tr = (
        _read("transfers.txt")
        .filter(pl.col("from_trip_id").is_in(active["trip_id"].implode()) & pl.col("to_trip_id").is_in(active["trip_id"].implode()))
        .collect()
        .join(platforms.select(pl.col("stop_id").alias("from_stop_id"), "station", pl.col("platform").alias("from_platform")), on="from_stop_id")
        .join(platforms.select(pl.col("stop_id").alias("to_stop_id"), pl.col("platform").alias("to_platform")), on="to_stop_id")
        .select(pl.col("from_trip_id").alias("from_trip"), pl.col("to_trip_id").alias("to_trip"), "station",
                "from_platform", "to_platform", pl.col("transfer_type").replace_strict(kinds, default="other").alias("kind"))
    )
    return DayTimetable(day, active.filter(pl.col("trip_id").is_in(st["trip_id"].unique().implode())), st, stations, tr)
