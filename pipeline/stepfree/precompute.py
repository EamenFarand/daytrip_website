"""Run the router for every origin and summarise the journeys per destination.

Per origin, day, profile, train set and change limit (0, 1, 2):
  median duration, fastest duration, departures per hour, changes and via
  stations of the median journey.

"Journeys" are the Pareto-optimal ones departing in the window: the options a
sensible traveller would actually take (no journey that leaves earlier and
arrives later than another).

Finally, more options never make a destination look worse: see
`more_options_never_worse`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import LATEST_ARRIVAL, MAX_TRANSFERS, WINDOW_END, WINDOW_START
from .network import Network, Profile
from .raptor import Journey, profile_search

WINDOW_HOURS = (WINDOW_END - WINDOW_START) / 60

# Each allows every journey the one before it does: a journey that works with a pram works for anyone,
# and one on sprinters works when intercities are allowed too.
PROFILE_ORDER = ("stroller", "any")
TRAIN_SET_ORDER = ("sprinter", "all")


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


def _trim(levels: list) -> list:
    """Drop trailing copies (a reader uses the last entry for higher change limits)."""
    while len(levels) > 1 and levels[-1] == levels[-2]:
        levels = levels[:-1]
    return levels


def encode_levels(levels: list[Summary | None]) -> list:
    """Results for 0, 1, 2 changes; trailing copies are dropped (use the last entry for higher limits)."""
    return _trim([lv.encode() if lv else None for lv in levels])


def expand_levels(entries: list | None) -> list:
    """Undo the trailing-copies encoding: exactly one entry (or None) per change limit."""
    if not entries:
        return [None] * (MAX_TRANSFERS + 1)
    return [entries[min(k, len(entries) - 1)] for k in range(MAX_TRANSFERS + 1)]


def _rank(entry: list) -> tuple:
    """Better: shorter typical time, then fewer changes, more departures, shorter fastest."""
    median, fastest, per_hour, changes = entry[:4]
    return (median, changes, -per_hour, fastest)


def more_options_never_worse(day: dict[str, dict[str, dict[str, list]]]) -> None:
    """Make each variant at least as good as every variant with fewer options (in place).

    `day[profile][train_set][dest]` holds encoded levels. The typical (median) time of the
    journeys isn't monotone by itself: allowing a change, intercities or no pram adds journeys
    at in-between times that are often slower, which pulls the median up. Utrecht C -> Abcoude:
    3 direct trains of 20 min, but with a change allowed the median became 31 min, so Abcoude
    dropped out of "30 min" when you allowed more. A traveller who may change can still go
    direct, so each entry becomes the best (by `_rank`) of its own and those of the variants
    with fewer options. On a tie the one with fewer options stays.
    """
    dests = {d for per_set in day.values() for dests in per_set.values() for d in dests}
    for dest in dests:
        best: dict[tuple[str, str], list] = {}
        for p_i, prof in enumerate(PROFILE_ORDER):
            for t_i, tset in enumerate(TRAIN_SET_ORDER):
                own = expand_levels(day.get(prof, {}).get(tset, {}).get(dest))
                row: list = []
                for k, entry in enumerate(own):
                    fewer = [row[k - 1]] if k else []
                    if p_i:
                        fewer.append(best[PROFILE_ORDER[p_i - 1], tset][k])
                    if t_i:
                        fewer.append(best[prof, TRAIN_SET_ORDER[t_i - 1]][k])
                    candidates = [e for e in [*fewer, entry] if e is not None]
                    row.append(min(candidates, key=_rank) if candidates else None)  # min keeps the first on ties
                best[prof, tset] = row
                if any(e is not None for e in row):
                    day.setdefault(prof, {}).setdefault(tset, {})[dest] = _trim(row)


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
