"""Checks a build must pass before it replaces the live one.

1. Structure: every file parses; entries are well-formed.
2. Invariants that must hold whatever the timetable:
   - the stroller profile is never faster than "any" (it only adds restrictions),
   - "sprinter" trains are never faster than "all" trains,
   - allowing more changes is never slower,
   - stroller results only end at step-free stations (or partly step-free ones).
3. A few known answers near Houten / Utrecht (full builds only).
"""

from __future__ import annotations

import json
from pathlib import Path


class ValidationError(Exception):
    pass


def _levels(entries: list | None) -> list:
    """Expand the trailing-copies encoding to exactly 3 levels."""
    if not entries:
        return [None, None, None]
    return [entries[min(k, len(entries) - 1)] for k in range(3)]


def validate(build: Path, partial: bool = False) -> None:
    errors: list[str] = []
    meta = json.loads((build / "meta.json").read_text(encoding="utf-8"))
    stations = {s["code"]: s for s in json.loads((build / "stations.json").read_text(encoding="utf-8"))}
    if not partial and len(stations) < 380:
        errors.append(f"only {len(stations)} stations")
    for s in stations.values():
        if s["status"] not in ("yes", "partial", "no", "unknown"):
            errors.append(f"{s['code']}: bad status {s['status']}")

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
                        prev = None
                        for k, e in enumerate(_levels(entries)):
                            if e is None:
                                continue
                            med, fast, per_hour, changes = e[:4]
                            via = e[4].split("|") if len(e) > 4 else []
                            if not (0 < fast <= med) or per_hour <= 0 or changes > k or len(via) != changes:
                                errors.append(f"{where} k={k}: malformed {e}")
                            if prev is not None and fast > prev:
                                errors.append(f"{where}: more changes allowed but slower ({prev} -> {fast})")
                            prev = fast
            # stroller never faster than any; sprinter never faster than all
            for (a_prof, a_set), (b_prof, b_set) in [(("stroller", "all"), ("any", "all")), (("stroller", "sprinter"), ("any", "sprinter")),
                                                   (("any", "sprinter"), ("any", "all")), (("stroller", "sprinter"), ("stroller", "all"))]:
                restricted = per_profile.get(a_prof, {}).get(a_set, {})
                free = per_profile.get(b_prof, {}).get(b_set, {})
                for dest, entries in restricted.items():
                    if dest not in free:
                        errors.append(f"{o}->{dest} {day}: reachable in {a_prof}/{a_set} but not in {b_prof}/{b_set}")
                        continue
                    for k, (x, y) in enumerate(zip(_levels(entries), _levels(free[dest]))):
                        if x is not None and (y is None or x[1] < y[1]):
                            errors.append(f"{o}->{dest} {day} k={k}: {a_prof}/{a_set} faster than {b_prof}/{b_set}")
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
        e = _levels(doc["results"].get("weekday", {}).get(prof, {}).get(tset, {}).get(d))[k]
        if e is None or e[0] > max_median or e[2] < min_per_hour:
            errors.append(f"known answer failed: {o}->{d} {prof}/{tset} k={k}: {e}")
    return errors
