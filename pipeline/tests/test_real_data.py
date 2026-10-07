"""Checks against the real timetable and the real build.

Skipped until the data has been downloaded / built:
  uv run python -m stepfree.build
Bounds are loose on purpose, so the tests survive normal timetable changes.
"""

import json
from datetime import date

import polars as pl
import pytest

from stepfree import access, gtfs, network, raptor
from stepfree.config import BUILD, CACHE, WINDOW_END, WINDOW_START
from stepfree.validate import validate

needs_build = pytest.mark.skipif(not (BUILD / "meta.json").exists(), reason="no build yet")
needs_data = pytest.mark.skipif(not (CACHE / "gtfs-nl" / "stop_times.txt").exists(), reason="GTFS not downloaded")


def result(origin, dest, day="weekday", prof="stroller", tset="sprinter"):
    doc = json.loads((BUILD / "origins" / f"{origin}.json").read_text(encoding="utf-8"))
    entries = doc["results"].get(day, {}).get(prof, {}).get(tset, {}).get(dest)
    return [entries[min(k, len(entries) - 1)] for k in range(3)] if entries else [None] * 3


@needs_build
def test_build_passes_validation():
    validate(BUILD)


@needs_build
@pytest.mark.parametrize(
    "origin, dest, prof, tset, lo, hi",
    [
        ("HTNC", "UT", "stroller", "sprinter", 10, 16),  # the plan's example: direct, 0 changes
        ("HTN", "UT", "stroller", "sprinter", 8, 14),
        ("UT", "HTNC", "stroller", "sprinter", 10, 16),
        ("HTNC", "GDM", "stroller", "sprinter", 11, 18),
        ("UT", "ASD", "any", "all", 24, 30),  # Intercity
        ("UT", "RTD", "any", "all", 34, 42),
        ("UT", "MT", "any", "all", 105, 125),
    ],
)
def test_direct_trains(origin, dest, prof, tset, lo, hi):
    zero_changes = result(origin, dest, prof=prof, tset=tset)[0]
    assert zero_changes is not None, "expected a direct train"
    median, fastest, per_hour, changes = zero_changes[:4]
    assert lo <= fastest <= median <= hi
    assert changes == 0 and per_hour >= 2


@needs_build
def test_houten_castellum_to_utrecht_runs_every_15_minutes():
    assert result("HTNC", "UT")[0][2] == pytest.approx(4.0, abs=0.5)


@needs_build
@pytest.mark.parametrize("dest", ["AHPR", "VG", "WF", "EHS"])  # not step-free or unknown
def test_stroller_never_ends_at_a_station_without_step_free_access(dest):
    for tset in ("all", "sprinter"):
        assert result("UT", dest, tset=tset) == [None] * 3
    stations = json.loads((BUILD / "stations.json").read_text(encoding="utf-8"))
    if dest not in {s["code"] for s in stations}:  # works can close a station for longer than the build looks ahead
        pytest.skip(f"{dest} has no trains on the build's days")
    assert result("UT", dest, prof="any", tset="all") != [None] * 3  # but they are reachable without a pram


@needs_data
def test_router_avoids_a_real_transfer_station_marked_not_step_free():
    """Houten Castellum -> Amersfoort normally changes at Utrecht Centraal.
    Mark Utrecht Centraal as not step-free: no stroller journey may change there any more."""
    trips, dates = gtfs.rail_trips(), gtfs.service_dates()
    iff = gtfs.iff_stations()
    nl = set(iff.filter(pl.col("country") == "NL")["code"])
    minutes = dict(zip(iff["code"], iff["transfer_min"]))
    tt = gtfs.day_timetable(gtfs.choose_days(gtfs.station_calls(trips, nl), trips, dates, date.today())["weekday"], trips, dates, nl)
    stations = access.load()
    net = network.build(tt, "all")
    o, d, ut = net.station_index["HTNC"], net.station_index["AMF"], net.station_index["UT"]

    def changes_at(stns, prof_name):
        prof = network.profile(net, prof_name, stns, minutes)
        found = raptor.profile_search(net, prof, o, WINDOW_START, WINDOW_END)
        journeys = [j for per_k in found.get(d, []) for j in per_k]
        return {net.stop_station[leg.alight_stop] for j in journeys for leg in j.legs[:-1]}, journeys

    before, _ = changes_at(stations, "stroller")
    assert ut in before, "expected the normal route to change at Utrecht Centraal"

    blocked = dict(stations)
    ut_station = stations["UT"]
    blocked["UT"] = access.Station(**{**ut_station.__dict__, "tracks": {t: "no" for t in ut_station.tracks}})
    after, journeys = changes_at(blocked, "stroller")
    assert ut not in after
    # the "any" profile still changes at Utrecht, so the difference is the step-free rule
    assert ut in changes_at(blocked, "any")[0]
