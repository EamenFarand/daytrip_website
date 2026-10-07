"""Turn one day's timetable into the arrays the router scans.

Stops are platforms (station + platform code), so transfer times and step-free
checks can depend on which two platforms you change between.

A Network is built once per (day, train set). A Profile adds what depends on
who is travelling: where you may start, end and change, and how long a change takes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import polars as pl

from .access import Station
from .config import DEFAULT_TRANSFER, MIN_SAME_PLATFORM, STROLLER_BUFFER, by_category, in_train_set
from .gtfs import DayTimetable

MAX_CONTINUATION_GAP = 5  # minutes a train may wait at a platform before continuing under a new number


@dataclass
class Route:
    """Trips with the same sequence of platforms, ordered so no trip overtakes another."""

    stops: list[int]
    trips: list[int] = field(default_factory=list)  # global trip index, earliest first
    arr: list[list[int]] = field(default_factory=list)  # arr[i][j]: arrival of trip j at stop i
    dep: list[list[int]] = field(default_factory=list)
    board: list[list[bool]] = field(default_factory=list)
    alight: list[list[bool]] = field(default_factory=list)


@dataclass
class Network:
    day: str
    train_set: str
    station_codes: list[str]
    station_index: dict[str, int]
    stop_station: list[int]
    stop_platform: list[str]
    station_stops: list[list[int]]
    routes: list[Route]
    routes_at: list[list[tuple[int, int]]]  # stop -> [(route, position in route)]
    trip_ids: list[str]  # global trip index -> GTFS trip id(s), "+"-joined when merged
    trip_labels: list[str]  # "Sprinter 7432"
    forbidden: set[tuple[int, int]]  # (arriving trip, departing trip) that NS says don't connect
    pair_min_gap: dict[tuple[int, int], int]  # (stop, stop) -> shortest connection NS explicitly allows
    # trips in the "sprinter" set only because NS marks them accessible: an intercity without steps (usually the ICNG)
    accessible_intercity: list[bool] = field(default_factory=list)


@dataclass
class Profile:
    name: str
    can_start: list[bool]  # may board here at the origin (reach the platform from the street)
    can_end: list[bool]  # may leave the station from this platform
    transfers: list[list[tuple[int, int]]]  # stop -> [(stop, minutes)] including itself


def _continuations(tt: DayTimetable, events: dict[str, list[dict]]) -> dict[str, str]:
    """Trains that end at a platform and continue from it under a new number (stay seated)."""
    nxt: dict[str, str] = {}
    ok = tt.transfers.filter(
        pl.col("kind").is_in(["possible", "guaranteed"]) & (pl.col("from_platform") == pl.col("to_platform"))
    )
    for row in ok.iter_rows(named=True):
        a, b = events.get(row["from_trip"]), events.get(row["to_trip"])
        if not a or not b or len(a) < 2 or len(b) < 2:
            continue
        last, first = a[-1], b[0]
        if last["station"] != row["station"] or first["station"] != row["station"]:
            continue
        if not 0 <= first["dep"] - last["arr"] <= MAX_CONTINUATION_GAP:
            continue
        if b[1]["station"] == a[-2]["station"]:
            continue  # turns back the way it came: a normal change, not a through train
        if row["from_trip"] in nxt:  # a train splitting two ways: keep it as a normal change
            nxt[row["from_trip"]] = ""
            continue
        nxt[row["from_trip"]] = row["to_trip"]
    return {k: v for k, v in nxt.items() if v}


def build(tt: DayTimetable, train_set: str, step_free: dict[str, bool] | None = None) -> Network:
    """`step_free`: NS's verdict per train number for this day (trains.verdicts); only the "sprinter" set uses it."""
    step_free = step_free or {}
    trips = tt.trips.filter(
        pl.struct("agency_name", "category", "train_number").map_elements(
            lambda s: in_train_set(s["agency_name"], s["category"], train_set, step_free.get(s["train_number"])),
            return_dtype=pl.Boolean,
        )
    )
    label = {r["trip_id"]: f"{r['category']} {r['train_number']}" for r in trips.iter_rows(named=True)}
    intercity = {r["trip_id"] for r in trips.iter_rows(named=True)
                 if train_set == "sprinter" and not by_category(r["agency_name"], r["category"])}
    events: dict[str, list[dict]] = defaultdict(list)
    for r in tt.stop_times.filter(pl.col("trip_id").is_in(trips["trip_id"].implode())).iter_rows(named=True):
        events[r["trip_id"]].append(r)
    events = {k: v for k, v in events.items() if len(v) >= 2}

    # merge through trains into one trip
    nxt = _continuations(tt, events)
    has_prev = set(nxt.values())
    merged: list[tuple[list[str], list[dict]]] = []
    for trip_id in events:
        if trip_id in has_prev:
            continue
        chain, seq = [trip_id], list(events[trip_id])
        while chain[-1] in nxt and nxt[chain[-1]] in events and nxt[chain[-1]] not in chain:
            b = events[nxt[chain[-1]]]
            join = dict(seq[-1])
            join.update(dep=b[0]["dep"], can_board=b[0]["can_board"])
            seq = seq[:-1] + [join] + b[1:]
            chain.append(nxt[chain[-1]])
        merged.append((chain, seq))

    # stops and stations
    station_codes = sorted({e["station"] for _, seq in merged for e in seq})
    station_index = {c: i for i, c in enumerate(station_codes)}
    stop_key: dict[tuple[str, str], int] = {}
    stop_station, stop_platform = [], []
    for _, seq in merged:
        for e in seq:
            key = (e["station"], e["platform"])
            if key not in stop_key:
                stop_key[key] = len(stop_station)
                stop_station.append(station_index[e["station"]])
                stop_platform.append(e["platform"])
    station_stops: list[list[int]] = [[] for _ in station_codes]
    for s, st in enumerate(stop_station):
        station_stops[st].append(s)

    # routes: group by platform sequence, split where a trip would overtake another
    trip_ids, trip_labels, accessible_intercity = [], [], []
    patterns: dict[tuple[int, ...], list[tuple[int, list[dict]]]] = defaultdict(list)
    trip_of: dict[str, int] = {}
    for chain, seq in merged:
        g = len(trip_ids)
        trip_ids.append("+".join(chain))
        trip_labels.append(" → ".join(dict.fromkeys(label[c] for c in chain)))
        accessible_intercity.append(any(c in intercity for c in chain))
        for c in chain:
            trip_of[c] = g
        patterns[tuple(stop_key[(e["station"], e["platform"])] for e in seq)].append((g, seq))
    routes: list[Route] = []
    for stops, members in patterns.items():
        members.sort(key=lambda m: (m[1][0]["dep"], m[1][-1]["arr"]))
        groups: list[Route] = []
        for g, seq in members:
            for r in groups:  # first route where this trip is not earlier than the last one anywhere
                if all(seq[i]["dep"] >= r.dep[i][-1] and seq[i]["arr"] >= r.arr[i][-1] for i in range(len(stops))):
                    break
            else:
                r = Route(list(stops), arr=[[] for _ in stops], dep=[[] for _ in stops],
                          board=[[] for _ in stops], alight=[[] for _ in stops])
                groups.append(r)
            r.trips.append(g)
            for i, e in enumerate(seq):
                r.arr[i].append(e["arr"])
                r.dep[i].append(e["dep"])
                r.board[i].append(e["can_board"])
                r.alight[i].append(e["can_alight"])
        routes.extend(groups)
    routes_at: list[list[tuple[int, int]]] = [[] for _ in stop_station]
    for ri, r in enumerate(routes):
        for i, s in enumerate(r.stops):
            routes_at[s].append((ri, i))

    # NS's trip-specific rules: connections it rules out, and short ones it explicitly allows
    times = {(tid, e["station"]): e for tid, seq in events.items() for e in seq}
    forbidden: set[tuple[int, int]] = set()
    pair_min_gap: dict[tuple[int, int], int] = {}
    for row in tt.transfers.iter_rows(named=True):
        a, b = trip_of.get(row["from_trip"]), trip_of.get(row["to_trip"])
        if a is None or b is None or a == b:
            continue
        if row["kind"] == "impossible":
            forbidden.add((a, b))
            continue
        ea, eb = times.get((row["from_trip"], row["station"])), times.get((row["to_trip"], row["station"]))
        pa, pb = stop_key.get((row["station"], row["from_platform"])), stop_key.get((row["station"], row["to_platform"]))
        if ea is None or eb is None or pa is None or pb is None:
            continue
        gap = eb["dep"] - ea["arr"]
        if gap >= 0:
            pair_min_gap[(pa, pb)] = min(gap, pair_min_gap.get((pa, pb), gap))

    return Network(
        day=tt.day.isoformat(), train_set=train_set, station_codes=station_codes, station_index=station_index,
        stop_station=stop_station, stop_platform=stop_platform, station_stops=station_stops, routes=routes,
        routes_at=routes_at, trip_ids=trip_ids, trip_labels=trip_labels, forbidden=forbidden, pair_min_gap=pair_min_gap,
        accessible_intercity=accessible_intercity,
    )


def profile(net: Network, name: str, access: dict[str, Station], transfer_minutes: dict[str, int]) -> Profile:
    """Where one may start, end and change for this profile ("any" or "stroller")."""
    stroller = name == "stroller"
    n = len(net.stop_station)
    step_free, surface = [], []
    for s in range(n):
        code, platform = net.station_codes[net.stop_station[s]], net.stop_platform[s]
        st = access.get(code)
        status = st.platform_status(platform) if st else "unknown"
        if st is not None and not st.knows(platform) and st.status == "yes":
            # Timetable and EPIAP number platforms differently (or the timetable gives none).
            # If every track EPIAP knows here is step-free and the timetable uses no more
            # platforms than EPIAP has, this platform is one of them: step-free.
            used = {net.stop_platform[p] for p in net.station_stops[net.stop_station[s]]} - {"?"}
            if len(used) <= len(st.main_tracks):
                status = "yes"
        step_free.append(status == "yes")
        surface.append(st.platform_surface(platform) if st else f"?{platform}")

    transfers: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for station, stops in enumerate(net.station_stops):
        base = transfer_minutes.get(net.station_codes[station]) or DEFAULT_TRANSFER
        for a in stops:
            for b in stops:
                same_surface = a == b or surface[a] == surface[b]
                if stroller and not same_surface and not (step_free[a] and step_free[b]):
                    continue  # would need stairs: not allowed with a pram
                minutes = MIN_SAME_PLATFORM if same_surface else base
                minutes = min(minutes, net.pair_min_gap.get((a, b), minutes))
                if stroller:
                    minutes += STROLLER_BUFFER
                transfers[a].append((b, minutes))

    if stroller:
        return Profile(name, can_start=step_free, can_end=step_free, transfers=transfers)
    return Profile(name, can_start=[True] * n, can_end=[True] * n, transfers=transfers)
