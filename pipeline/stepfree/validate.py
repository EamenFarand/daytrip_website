"""Checks a build must pass before it replaces the live one.

`check_router`, on the router's raw output (before `more_options_never_worse`):
  more options never make the fastest journey slower or a destination unreachable:
  "any" vs stroller, "all" vs "sprinter" trains, and more changes allowed.
  Anything else is a router bug.

`validate`, on the files the site loads:
1. Structure: every file parses; entries are well-formed.
2. What the visitor sees stays consistent: allowing more (changes, intercities,
   no pram) never gives a longer typical time, so a station never drops out
   of a time filter when you widen your choices.
3. Stroller results only end at step-free stations (or partly step-free ones).
4. A few known answers near Houten / Utrecht (full builds only).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .precompute import expand_levels

MEDIAN, FASTEST = 0, 1  # positions in an entry

# (fewer options, more options): the second allows every journey the first does
EDGES = [
    (("stroller", "all"), ("any", "all")),
    (("stroller", "sprinter"), ("any", "sprinter")),
    (("any", "sprinter"), ("any", "all")),
    (("stroller", "sprinter"), ("stroller", "all")),
]


class ValidationError(Exception):
    pass


def _never_worse(origin: str, results: dict, field: int, worse: str) -> list[str]:
    """With more options, entry[field] must not go up and a journey must not disappear."""
    errors = []
    for day, per_profile in results.items():
        for prof, per_set in per_profile.items():
            for tset, dests in per_set.items():
                for dest, entries in dests.items():
                    lv = expand_levels(entries)
                    for k in range(1, len(lv)):
                        a, b = lv[k - 1], lv[k]
                        if a is not None and (b is None or b[field] > a[field]):
                            errors.append(f"{origin}->{dest} {day}/{prof}/{tset}: {k} changes allowed but {worse} than {k - 1} ({a} -> {b})")
        for (a_prof, a_set), (b_prof, b_set) in EDGES:
            fewer = per_profile.get(a_prof, {}).get(a_set, {})
            more = per_profile.get(b_prof, {}).get(b_set, {})
            for dest, entries in fewer.items():
                for k, (x, y) in enumerate(zip(expand_levels(entries), expand_levels(more.get(dest)))):
                    if x is not None and (y is None or y[field] > x[field]):
                        errors.append(f"{origin}->{dest} {day} k={k}: {b_prof}/{b_set} {worse} than {a_prof}/{a_set} ({x} vs {y})")
    return errors


def check_router(results: dict[str, dict]) -> None:
    """`results[origin]` as the router produced it: more options must never be slower."""
    errors: list[str] = []
    for origin, per_day in results.items():
        errors += _never_worse(origin, per_day, FASTEST, "slower")
        if len(errors) > 50:
            break
    if errors:
        raise ValidationError(f"router: {len(errors)} problems, first ones:\n" + "\n".join(errors[:30]))


def validate(build: Path, partial: bool = False) -> None:
    errors: list[str] = []
    meta = json.loads((build / "meta.json").read_text(encoding="utf-8"))
    stations = {s["code"]: s for s in json.loads((build / "stations.json").read_text(encoding="utf-8"))}
    if not partial and len(stations) < 380:
        errors.append(f"only {len(stations)} stations")
    for s in stations.values():
        if s["status"] not in ("yes", "partial", "no", "unknown"):
            errors.append(f"{s['code']}: bad status {s['status']}")
        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", s.get("slug") or ""):
            errors.append(f"{s['code']}: bad page name {s.get('slug')!r}")
    doubles = [slug for slug, n in Counter(s.get("slug") for s in stations.values()).items() if n > 1]
    if doubles:
        errors.append(f"two stations share a page name: {doubles}")

    files = sorted((build / "origins").glob("*.json"))
    if not partial and len(files) < 380:
        errors.append(f"only {len(files)} origin files")
    for f in files:
        doc = json.loads(f.read_text(encoding="utf-8"))
        o = doc["origin"]
        for day, per_profile in doc["results"].items():
            for prof, per_set in per_profile.items():
                for tset, dests in per_set.items():
                    for dest, entries in dests.items():
                        where = f"{o}->{dest} {day}/{prof}/{tset}"
                        if dest not in stations:
                            errors.append(f"{where}: unknown destination")
                        if prof == "stroller" and stations.get(dest, {}).get("status") not in ("yes", "partial"):
                            errors.append(f"{where}: stroller journey to a station that isn't step-free")
                        for k, e in enumerate(expand_levels(entries)):
                            if e is None:
                                continue
                            med, fast, per_hour, changes = e[:4]
                            via = e[4].split("|") if len(e) > 4 and e[4] else []
                            tracks = e[5].split("|") if len(e) > 5 else None
                            if not (0 < fast <= med) or per_hour <= 0 or changes > k or len(via) != changes:
                                errors.append(f"{where} k={k}: malformed {e}")
                            elif tracks is not None and len(tracks) != 2 + 2 * changes:
                                errors.append(f"{where} k={k}: tracks don't fit the changes {e}")
        errors += _never_worse(o, doc["results"], MEDIAN, "a longer typical time")
        if len(errors) > 50:
            break

    if not partial:
        errors += _known_answers(build)
    if errors:
        raise ValidationError(f"{len(errors)} problems, first ones:\n" + "\n".join(errors[:30]))
    print(f"validation passed ({len(files)} origin files, {len(stations)} stations)")


def _known_answers(build: Path) -> list[str]:
    """Pairs whose answer we know. Loose bounds: they should survive timetable changes."""
    checks = [
        # origin, dest, profile, train set, max changes, max median minutes, min departures per hour
        ("HTNC", "UT", "stroller", "sprinter", 0, 20, 2),  # direct Sprinter, ~13 min
        ("HTN", "UT", "stroller", "sprinter", 0, 17, 2),
        ("UT", "ASD", "any", "all", 0, 35, 2),  # direct Intercity, ~27 min
        ("UT", "HTNC", "stroller", "sprinter", 0, 20, 2),
    ]
    errors = []
    for o, d, prof, tset, k, max_median, min_per_hour in checks:
        doc = json.loads((build / "origins" / f"{o}.json").read_text(encoding="utf-8"))
        e = expand_levels(doc["results"].get("weekday", {}).get(prof, {}).get(tset, {}).get(d))[k]
        if e is None or e[0] > max_median or e[2] < min_per_hour:
            errors.append(f"known answer failed: {o}->{d} {prof}/{tset} k={k}: {e}")
    return errors
