"""Q5: what the live lift feed looks like, from the log written by lift_listener.py.

Usage:  uv run python lift_analysis.py
Reads:  <cache>/lifts/siri_fm_*.jsonl, and stations.json from the pipeline build (to tie lifts to stations).

Answers: how complete the log is, when the daily full state arrives, how many lifts are out,
how much changes between two daily snapshots, and how quickly changes are pushed.
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

from fetch import RAW, ROOT

LOCAL = timezone(timedelta(hours=2), "CEST")  # the whole log falls in summer time
SNAPSHOT_MIN = 400  # a delivery with at least this many lifts is the daily full state
OFFLINE = timedelta(minutes=25)  # heartbeats come every 10 minutes; a longer silence = listener down
PREFIX = "NL:CHB:LiftEquipment:"


def _setting(key: str, default: Path) -> Path:
    value = os.environ.get(key)
    env_file = ROOT / ".env"
    if not value and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == key and v.strip():
                value = v.strip()
    return Path(value) if value else default


def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _local(t: datetime) -> str:
    return t.astimezone(LOCAL).strftime("%a %d %b %H:%M")


def load() -> list[dict]:
    rows = []
    for f in sorted((RAW / "lifts").glob("siri_fm_*.jsonl")):
        rows += [json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
    for r in rows:
        r["t"] = _time(r["received"])
    return sorted(rows, key=lambda r: r["t"])


def main() -> None:
    rows = load()
    first, last = rows[0]["t"], rows[-1]["t"]
    gaps = [(a["t"], b["t"]) for a, b in zip(rows, rows[1:]) if b["t"] - a["t"] > OFFLINE]
    offline = sum((b - a for a, b in gaps), timedelta())
    print(f"Log: {_local(first)} to {_local(last)} ({(last - first) / timedelta(hours=1):.0f} h), "
          f"{len(rows)} lines; listener offline {offline / timedelta(hours=1):.1f} h:")
    for a, b in gaps:
        print(f"  no messages {_local(a)} - {_local(b)}")

    beats = [r["t"] for r in rows if r.get("heartbeat")]
    intervals = [b - a for a, b in zip(beats, beats[1:]) if b - a < OFFLINE]
    print(f"Heartbeats: {len(beats)}, typically every {median(intervals) / timedelta(minutes=1):.0f} min")

    conditions = [r for r in rows if r.get("facility")]
    snapshots: dict[str, list[dict]] = defaultdict(list)
    changes = []
    for r in conditions:
        (snapshots[r["delivery_ts"]] if r["delivery_size"] >= SNAPSHOT_MIN else changes).append(r)
    snaps = sorted(snapshots.items())

    stations = json.loads((_setting("STEPFREE_BUILD", ROOT / "data" / "build") / "stations.json").read_text(encoding="utf-8"))
    lift_station = {lf["id"]: (s["code"], lf) for s in stations for lf in s["lifts"]}

    print("\nDaily full state:")
    for ts, msgs in snaps:
        status = Counter(m["status"] for m in msgs)
        print(f"  {_local(_time(ts))}: {len(msgs)} lifts, " + ", ".join(f"{k} {v}" for k, v in status.most_common()))
    ts, msgs = snaps[-1]
    at = _time(ts)
    ids = {m["facility"].removeprefix(PREFIX) for m in msgs}
    per_lift = Counter(m["facility"] for m in msgs)
    doubles = [f for f, n in per_lift.items() if n > 1]
    combos = Counter(tuple(sorted(m["status"] + ("+end" if m["end"] else "") for m in msgs if m["facility"] == f)) for f in doubles)
    print(f"  {len(ids)} distinct lifts; {len(doubles)} appear more than once: "
          + ", ".join(f"{'/'.join(c)} x{n}" for c, n in combos.most_common()))
    print(f"  tied to a station in stations.json: {len(ids & lift_station.keys())} of {len(ids)}"
          f" (stations.json lists {len(lift_station)} lifts)")
    out = [m for m in msgs if m["status"] != "available"]
    ages = Counter()
    for m in out:
        age = at - _time(m["start"]) if m["start"] else None
        ages["no start date" if age is None else "out > 30 days" if age > timedelta(days=30)
             else "out 1-30 days" if age > timedelta(days=1) else "out < 1 day"] += 1
    serving = sum(1 for m in out if lift_station.get(m["facility"].removeprefix(PREFIX), (None, {"tracks": []}))[1]["tracks"])
    print(f"  not available on {_local(at)}: {len(out)} ({', '.join(f'{k} {v}' for k, v in ages.most_common())});"
          f" {serving} of them serve a platform track")
    planned = sum(1 for m in out if m["end"])
    print(f"  with a planned end date: {planned}")

    print("\nChanges between the daily states:")
    known: dict[str, str] = {}
    per_day: dict = defaultdict(lambda: [0, 0, set()])  # messages, real changes, lifts that changed
    for r in conditions:
        day = per_day[r["t"].astimezone(LOCAL).date()]
        if r["delivery_size"] < SNAPSHOT_MIN:
            day[0] += 1
            if known.get(r["facility"], r["status"]) != r["status"]:
                day[1] += 1
                day[2].add(r["facility"])
        known[r["facility"]] = r["status"]
    for day, (n, real, lifts) in sorted(per_day.items()):
        print(f"  {day}: {n} status messages, {real} of them a real change, for {len(lifts)} lifts")
    lags = [r["t"] - _time(r["start"]) for r in changes if r["start"]]
    lags = [lag for lag in lags if timedelta(0) <= lag <= timedelta(hours=6)]
    if lags:
        lags.sort()
        print(f"  pushed after the change: median {median(lags).total_seconds() / 60:.1f} min, "
              f"90% within {lags[int(len(lags) * 0.9)].total_seconds() / 60:.1f} min ({len(lags)} messages)")

    print("\nWhat a once-a-day snapshot would miss (between consecutive full states):")
    for (ts_a, a), (ts_b, b) in zip(snaps, snaps[1:]):
        start, end = _time(ts_a), _time(ts_b)
        published = {m["facility"]: m["status"] for m in a}
        state = dict(published)
        missed = wrong_alarm = 0.0  # lift-hours: really out but shown available / the reverse
        went_out = set()
        last_t = start
        window = [r for r in changes if start < r["t"] < end]
        for r in window + [{"t": end}]:
            hours = (r["t"] - last_t) / timedelta(hours=1)
            for f, s in state.items():
                p = published.get(f, "unknown")
                if s != "available" and p == "available":
                    missed += hours
                elif s == "available" and p != "available":
                    wrong_alarm += hours
            last_t = r["t"]
            if "facility" in r:
                state[r["facility"]] = r["status"]
                if r["status"] != "available":
                    went_out.add(r["facility"])
        span = (end - start) / timedelta(hours=1)
        diff = sum(1 for m in b if state.get(m["facility"]) != m["status"])
        offline_here = [g for g in gaps if start < g[0] < end]
        print(f"  {_local(start)} -> {_local(end)}: {len(window)} changes, {len(went_out)} lifts went out at some point;"
              f" on average {missed / span:.1f} lifts really out but shown working, {wrong_alarm / span:.1f} the reverse;"
              f" next full state differs from changes-applied state for {diff} lifts"
              + (" (listener was offline in this period)" if offline_here else ""))


if __name__ == "__main__":
    main()
