"""Run the router for every origin and summarise the journeys per destination.

Per origin, day, profile, train set and change limit (0, 1, 2):
  median duration, fastest duration, departures per hour, changes and via
  stations of the median journey.

"Journeys" are the Pareto-optimal ones departing in the window: the options a
sensible traveller would actually take (no journey that leaves earlier and
arrives later than another).
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import LATEST_ARRIVAL, MAX_TRANSFERS, WINDOW_END, WINDOW_START
from .network import Network, Profile
from .raptor import Journey, profile_search

WINDOW_HOURS = (WINDOW_END - WINDOW_START) / 60


@dataclass(frozen=True)
class Summary:
    median: int
    fastest: int
    per_hour: float
    changes: int
    via: tuple[str, ...]

    def encode(self) -> list:
        out = [self.median, self.fastest, self.per_hour, self.changes]
        if self.via:
            out.append("|".join(self.via))
        return out


def summarise(net: Network, journeys: list[Journey]) -> Summary | None:
    if not journeys:
        return None
    by_duration = sorted(journeys, key=lambda j: (j.duration, j.changes, -j.dep))
    typical = by_duration[(len(by_duration) - 1) // 2]  # lower median: always a real journey
    via = tuple(net.station_codes[net.stop_station[leg.alight_stop]] for leg in typical.legs[:-1])
    return Summary(
        median=typical.duration,
        fastest=by_duration[0].duration,
        per_hour=round(len(journeys) / WINDOW_HOURS, 1),
        changes=typical.changes,
        via=via,
    )


def encode_levels(levels: list[Summary | None]) -> list:
    """Results for 0, 1, 2 changes; trailing copies are dropped (use the last entry for higher limits)."""
    while len(levels) > 1 and levels[-1] == levels[-2]:
        levels = levels[:-1]
    return [lv.encode() if lv else None for lv in levels]


def origin_results(net: Network, prof: Profile, origin_code: str) -> dict[str, list]:
    origin = net.station_index.get(origin_code)
    if origin is None:
        return {}
    found = profile_search(net, prof, origin, WINDOW_START, WINDOW_END,
                           max_trains=MAX_TRANSFERS + 1, latest_arrival=LATEST_ARRIVAL)
    out = {}
    for station, per_limit in found.items():
        levels = [summarise(net, js) for js in per_limit]
        if any(levels):
            out[net.station_codes[station]] = encode_levels(levels)
    return dict(sorted(out.items()))
