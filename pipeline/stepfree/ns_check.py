"""Compare our journeys with the NS journey planner for ~20 station pairs.

Needs NS_API_KEY (NS "Reisinformatie API", in .env). Run: `uv run python -m stepfree.ns_check`
For each pair: the fastest journey leaving between 10:00 and 11:00 on the build's weekday,
from our router ("any" profile, all trains) and from NS. Prints a table and returns mismatches.
"""

from __future__ import annotations

import time
from datetime import date, datetime

import polars as pl
import requests

from . import access, gtfs, network, raptor
from .config import USER_AGENT, env

NS_TRIPS = "https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips"
PAIRS = [
    ("HTNC", "UT"), ("HTN", "GDM"), ("UT", "ASD"), ("UT", "RTD"), ("UT", "AMF"), ("ASD", "SHL"), ("RTD", "GVC"),
    ("UT", "ZL"), ("AMF", "ZL"), ("EHV", "UT"), ("NM", "UT"), ("AH", "UT"), ("GN", "LW"), ("HT", "EHV"),
    ("UT", "MT"), ("ASD", "ALM"), ("ZVT", "ASD"), ("HLM", "ASD"), ("LEDN", "GVC"), ("BD", "RTD"),
]
FROM, TO = 10 * 60, 11 * 60
TOLERANCE = 5  # minutes, or 10% for long journeys


def ns_fastest(key: str, origin: str, dest: str, day: date) -> tuple[int, int] | None:
    """(duration, changes) of NS's fastest trip leaving between FROM and TO, or None."""
    params = {"fromStation": origin, "toStation": dest, "dateTime": f"{day.isoformat()}T10:00:00+02:00"}
    headers = {"Ocp-Apim-Subscription-Key": key, "User-Agent": USER_AGENT}
    r = requests.get(NS_TRIPS, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    best = None
    for trip in r.json().get("trips", []):
        dep = datetime.strptime(trip["legs"][0]["origin"]["plannedDateTime"], "%Y-%m-%dT%H:%M:%S%z")
        minute = dep.hour * 60 + dep.minute
        if FROM <= minute <= TO and not trip.get("status") == "CANCELLED":
            cand = (trip["plannedDurationInMinutes"], trip["transfers"])
            best = cand if best is None or cand < best else best
    return best


def compare() -> list[str]:
    key = env("NS_API_KEY")
    if not key:
        raise RuntimeError("NS_API_KEY is not set (see docs/NEEDS_DAAN.md)")
    trips, dates = gtfs.rail_trips(), gtfs.service_dates()
    iff = gtfs.iff_stations()
    nl = set(iff.filter(pl.col("country") == "NL")["code"])
    minutes = dict(zip(iff["code"], iff["transfer_min"]))
    day = gtfs.choose_days(trips, dates, date.today())["weekday"]
    net = network.build(gtfs.day_timetable(day, trips, dates, nl), "all")
    prof = network.profile(net, "any", access.load(), minutes)

    problems = []
    print(f"{'pair':<12}{'ours':>12}{'NS':>12}  verdict   ({day})")
    for origin, dest in PAIRS:
        found = raptor.profile_search(net, prof, net.station_index[origin], FROM, TO)
        journeys = found.get(net.station_index[dest], [[], [], []])[2]
        ours = min(((j.duration, j.changes) for j in journeys), default=None)
        theirs = ns_fastest(key, origin, dest, day)
        time.sleep(1)  # be polite to the API
        ok = ours is not None and theirs is not None and abs(ours[0] - theirs[0]) <= max(TOLERANCE, 0.1 * theirs[0])
        print(f"{origin + '-' + dest:<12}{str(ours):>12}{str(theirs):>12}  {'ok' if ok else 'CHECK'}")
        if not ok:
            problems.append(f"{origin}-{dest}: ours {ours}, NS {theirs}")
    return problems


if __name__ == "__main__":
    issues = compare()
    print(f"\n{len(PAIRS) - len(issues)}/{len(PAIRS)} within tolerance")
