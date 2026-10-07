"""Which trains run without steps, from NS's own data (docs/DECISIONS.md, 2026-10-07).

The listener on Daan's home server (lifts/) follows NS's journey messages (InfoPlus RIT via NDOV Loket, CC0),
in which NS marks every train unit accessible or not. Per service date it publishes which train numbers ran
with accessible units only ("yes") and which with at least one that isn't ("no"); the site serves that at
/api/trains.

For a reference day, per train number, counting the dates of the same day type (Mon-Fri, or Saturday) in the
last four weeks that belong to the same yearly timetable:
- seen once with a unit that isn't accessible: not without steps, whatever its category;
- seen on at least MIN_DAYS dates, always with accessible units only: without steps, an intercity too;
- anything else: no verdict, and the category rule decides (config.in_train_set).
Without a recent record there are no verdicts, and the build works as it did before.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from .config import CACHE, env
from .fetch import fetch
from .gtfs import timetable_change

TRAINS_URL = "https://trapvrij.nl/api/trains"
MIN_DAYS = 3  # an intercity counts once NS marked it accessible on this many dates (and never not)
WINDOW = timedelta(days=28)
MAX_AGE = timedelta(days=14)  # an older record is not used at all


def load(now: datetime | None = None) -> dict | None:
    """The listener's record, freshly downloaded or else the last downloaded copy; None if there is none or it's too old.

    STEPFREE_TRAINS (a file) replaces the download, for local runs and tests.
    """
    if local := env("STEPFREE_TRAINS"):
        path = Path(local)
    else:
        try:
            path = fetch(TRAINS_URL, "trains.json", timeout=60)
        except requests.RequestException as e:
            path = CACHE / "trains.json"
            _say(f"trains: download failed ({e}); {'using the last copy' if path.exists() else 'none kept'}")
    if not path.exists():
        return None
    record = json.loads(path.read_text(encoding="utf-8"))
    updated = datetime.fromisoformat(record["updated"].replace("Z", "+00:00"))
    if record.get("v") != 1 or (now or datetime.now(timezone.utc)) - updated > MAX_AGE:
        _say(f"trains: the record of {record['updated']} is too old (or of an unknown kind); not used")
        return None
    return record


def _say(text: str) -> None:
    """To stderr: stepfree.inputs' stdout goes to GitHub Actions as key=value lines."""
    print(text, file=sys.stderr)


def _kind(d: date) -> str | None:
    return "saturday" if d.weekday() == 5 else "weekday" if d.weekday() < 5 else None


def _timetable(day: date) -> tuple[date, date]:
    """The yearly timetable `day` belongs to: from its first day up to the next one's."""
    end = timetable_change(day)
    return timetable_change(date(end.year - 1, 1, 1)), end


def verdicts(record: dict | None, day: date) -> dict[str, bool]:
    """Train number -> without steps (True) or not (False), for the trains with a verdict for `day`."""
    if not record:
        return {}
    first, end = _timetable(day)
    oldest = date.fromisoformat(record["updated"][:10]) - WINDOW
    counts: dict[str, list[int]] = {}  # train number -> [dates accessible only, dates not]
    for d, marked in record["days"].items():
        when = date.fromisoformat(d)
        if _kind(when) != _kind(day) or not (first <= when < end) or when < oldest:
            continue
        for i, kind in enumerate(("yes", "no")):
            for number in marked[kind].split():
                counts.setdefault(number, [0, 0])[i] += 1
    return {n: no == 0 for n, (yes, no) in counts.items() if no or yes >= MIN_DAYS}


def summary(found: dict[str, bool]) -> dict[str, int]:
    return {"without_steps": sum(found.values()), "with_steps": sum(not v for v in found.values())}


def digest(record: dict | None, today: date) -> str:
    """A short hash of the verdicts for the coming Wednesday and Saturday: changes when a verdict does (stepfree.inputs)."""
    if not record:
        return "none"
    days = [today + timedelta(days=(target - today.weekday()) % 7 or 7) for target in (2, 5)]
    lines = [f"{d.weekday()} {n} {int(v)}" for d in days for n, v in sorted(verdicts(record, d).items())]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]
