"""Build small hand-made timetables for router tests."""

from __future__ import annotations

from datetime import date

import polars as pl

from stepfree.access import Station
from stepfree.gtfs import DayTimetable


def hm(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def timetable(trips: dict[str, list[tuple[str, str, str, str]]], transfers: list[tuple] = (),
              categories: dict[str, tuple[str, str]] | None = None) -> DayTimetable:
    """trips: {trip_id: [(station, platform, "arr", "dep"), ...]}; transfers: (from, to, station, from_pl, to_pl, kind)."""
    categories = categories or {}
    trip_rows, st_rows, stations = [], [], set()
    for tid, stops in trips.items():
        agency, cat = categories.get(tid, ("NS", "Sprinter"))
        trip_rows.append({"trip_id": tid, "agency_name": agency, "category": cat, "train_number": tid})
        for seq, (station, platform, arr, dep) in enumerate(stops, 1):
            stations.add(station)
            st_rows.append({"trip_id": tid, "seq": seq, "station": station, "platform": platform,
                            "arr": hm(arr), "dep": hm(dep), "can_board": seq < len(stops), "can_alight": seq > 1})
    tr = pl.DataFrame(
        [dict(zip(["from_trip", "to_trip", "station", "from_platform", "to_platform", "kind"], t)) for t in transfers],
        schema={"from_trip": pl.String, "to_trip": pl.String, "station": pl.String, "from_platform": pl.String,
                "to_platform": pl.String, "kind": pl.String},
    )
    return DayTimetable(
        day=date(2026, 10, 21),
        trips=pl.DataFrame(trip_rows),
        stop_times=pl.DataFrame(st_rows).with_columns(pl.col("seq").cast(pl.Int32), pl.col("arr").cast(pl.Int32),
                                                      pl.col("dep").cast(pl.Int32)),
        stations=pl.DataFrame([{"code": s, "name": s, "lat": 52.0, "lon": 5.0} for s in sorted(stations)]),
        transfers=tr,
    )


def station(code: str, tracks: dict[str, str], islands: dict[str, list[str]] | None = None) -> Station:
    """tracks: {"1": "yes"}; islands: {"1-2": ["1", "2"]} puts those tracks on one platform."""
    islands = islands or {}
    surface = {t: f"{code}:{t}" for t in tracks}
    for name, members in islands.items():
        for t in members:
            surface[t] = f"{code}:{name}"
    return Station(code=code, uic="0", name=code, tracks=dict(tracks), islands=dict(islands),
                   surface=surface, main_tracks=list(tracks))
