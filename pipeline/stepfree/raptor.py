"""Round-based public transit routing (RAPTOR), range version, one origin to all stations.

Delling, Pajor, Werneck (2012), "Round-Based Public Transit Routing". Departures
from the origin are processed from latest to earliest and labels are kept between
them ("rRAPTOR"): an earlier departure can always wait for a later one, so old
labels stay valid upper bounds. Round k = at most k trains = at most k-1 changes.

Stops are platforms. Accessibility is enforced *during* the search, through the
Profile: where you may board at the origin, where you may leave at the
destination, and which platform-to-platform changes exist (and how long they take).

Labels are cumulative: arr[k][p] is the earliest arrival at p using at most k
trains, so the "at most k changes" answers fall out directly.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from .network import Network, Profile

INF = 1 << 30
ORIGIN = ("origin",)


@dataclass
class Leg:
    trip: int
    board_stop: int
    alight_stop: int
    dep: int
    arr: int


@dataclass
class Journey:
    dep: int
    arr: int
    legs: list[Leg]

    @property
    def duration(self) -> int:
        return self.arr - self.dep

    @property
    def changes(self) -> int:
        return len(self.legs) - 1


def departures(net: Network, prof: Profile, origin: int, start: int, end: int) -> list[int]:
    """Times at which a train can be boarded at the origin within the window, latest first."""
    times = set()
    for p in net.station_stops[origin]:
        if not prof.can_start[p]:
            continue
        for ri, i in net.routes_at[p]:
            r = net.routes[ri]
            for j, d in enumerate(r.dep[i]):
                if start <= d <= end and r.board[i][j] and i < len(r.stops) - 1:
                    times.add(d)
    return sorted(times, reverse=True)


def profile_search(net: Network, prof: Profile, origin: int, start: int, end: int,
                   max_trains: int = 3, latest_arrival: int = INF) -> dict[int, list[list[Journey]]]:
    """All Pareto-optimal journeys (later departure, earlier arrival) from origin, per train limit.

    Returns {station: [journeys with <=1 train, <=2 trains, ...]}; each list is ordered by
    departure time (latest first). Only trains leaving the origin within [start, end] are
    used, and journeys are compared only with each other: a journey leaving after the window
    never hides one inside it.
    """
    n_stops = len(net.stop_station)
    K = max_trains
    arr = [[INF] * n_stops for _ in range(K + 1)]
    brd = [[INF] * n_stops for _ in range(K + 1)]
    arr_ptr: list[list] = [[None] * n_stops for _ in range(K + 1)]  # (trip, board_stop, dep, arr, round)
    brd_ptr: list[list] = [[None] * n_stops for _ in range(K + 1)]  # (from_stop, round) or ORIGIN
    best = [[INF] * len(net.station_codes) for _ in range(K + 1)]
    results: dict[int, list[list[Journey]]] = {}
    origin_stops = [p for p in net.station_stops[origin] if prof.can_start[p]]
    routes, routes_at, forbidden = net.routes, net.routes_at, net.forbidden
    stop_station, can_end = net.stop_station, prof.can_end

    def set_arr(k: int, p: int, value: int, ptr) -> None:
        for kk in range(k, K + 1):  # keep labels cumulative: "at most kk trains"
            if value < arr[kk][p]:
                arr[kk][p] = value
                arr_ptr[kk][p] = ptr
            else:
                break

    def set_brd(k: int, p: int, value: int, ptr) -> bool:
        if value >= brd[k][p]:
            return False
        for kk in range(k, K + 1):
            if value < brd[kk][p]:
                brd[kk][p] = value
                brd_ptr[kk][p] = ptr
            else:
                break
        return True

    def arriving_trip(k: int, p: int) -> int | None:
        """The train you arrived on before walking to p (for NS's ruled-out connections)."""
        bp = brd_ptr[k][p]
        if bp is None or bp is ORIGIN:
            return None
        from_stop, rnd = bp
        ap = arr_ptr[rnd][from_stop]
        return ap[0] if ap else None

    def journey(k: int, p: int, dep_time: int) -> Journey:
        legs: list[Leg] = []
        ptr = arr_ptr[k][p]
        alight = p
        while ptr is not None:
            trip, bstop, dep, a, rnd = ptr
            legs.append(Leg(trip, bstop, alight, dep, a))
            bp = brd_ptr[rnd - 1][bstop]
            if bp is ORIGIN or bp is None:
                break
            alight, prev_round = bp
            ptr = arr_ptr[prev_round][alight]
        legs.reverse()
        return Journey(dep_time, legs[-1].arr, legs)

    for tau in departures(net, prof, origin, start, end):
        marked = set()
        for p in origin_stops:
            if set_brd(0, p, tau, ORIGIN):
                marked.add(p)
        touched: set[int] = set()
        for k in range(1, K + 1):
            if not marked:
                break
            queue: dict[int, int] = {}
            for p in marked:
                for ri, i in routes_at[p]:
                    if i < queue.get(ri, INF):
                        queue[ri] = i
            improved: list[int] = []
            for ri, i0 in queue.items():
                r = routes[ri]
                stops, n_trips = r.stops, len(r.trips)
                t = -1  # position of the trip we're on, -1 = none
                t_board = t_dep = -1
                for i in range(i0, len(stops)):
                    p = stops[i]
                    if t >= 0 and r.alight[i][t]:
                        a = r.arr[i][t]
                        if a < arr[k][p] and a <= latest_arrival:
                            set_arr(k, p, a, (r.trips[t], t_board, t_dep, a, k))
                            improved.append(p)
                    b = brd[k - 1][p]
                    if b < INF and (t < 0 or b <= r.dep[i][t]):
                        j = bisect_left(r.dep[i], b)
                        came_on = arriving_trip(k - 1, p) if k > 1 else None
                        while j < n_trips and (not r.board[i][j] or (came_on is not None and (came_on, r.trips[j]) in forbidden)):
                            j += 1
                        if k == 1 and j < n_trips and r.dep[i][j] > end:
                            j = n_trips  # first train must leave the origin within the window
                        if j < n_trips and (t < 0 or j < t) and i < len(stops) - 1:
                            t, t_board, t_dep = j, p, r.dep[i][j]
            marked = set()
            for p1 in set(improved):
                touched.add(stop_station[p1])
                a = arr[k][p1]
                for p2, minutes in prof.transfers[p1]:
                    if set_brd(k, p2, a + minutes, (p1, k)):
                        marked.add(p2)

        for station in touched:
            if station == origin:
                continue
            exits = [p for p in net.station_stops[station] if can_end[p]]
            if not exits:
                continue
            for k in range(1, K + 1):
                p = min(exits, key=lambda s: arr[k][s])
                if arr[k][p] < best[k][station]:
                    best[k][station] = arr[k][p]
                    lists = results.setdefault(station, [[] for _ in range(K)])
                    lists[k - 1].append(journey(k, p, tau))
    return results
