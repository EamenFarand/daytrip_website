"""Build everything the site loads: `uv run python -m stepfree.build`.

Writes to data/build.tmp/, checks it, then swaps it into data/build/, so a
failing run never replaces the last good build.

  data/build/meta.json             when, from which data, with which rules
  data/build/stations.json         every station: name, position, step-free status, source
  data/build/origins/<CODE>.json   journeys from that station to every reachable station
"""

from __future__ import annotations

import argparse
import json
import multiprocessing
import os
import re
import shutil
import time
import unicodedata
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import date, datetime, timezone

import polars as pl

from . import access, config, gtfs, inputs, network
from .config import BUILD, DAY_TYPES, PROFILES, TRAIN_SETS
from .precompute import more_options_never_worse, origin_results
from .validate import check_router, validate

FORMAT_VERSION = 1


def slugify(name: str) -> str:
    """A readable URL name: "'s-Hertogenbosch Oost" -> "s-hertogenbosch-oost"."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def unique_slugs(names: dict[str, str]) -> dict[str, str]:
    """code -> slug for station pages; a name that would collide gets its code appended."""
    counts = Counter(slugify(n) for n in names.values())
    return {code: slugify(n) if counts[slugify(n)] == 1 else f"{slugify(n)}-{code.lower()}" for code, n in names.items()}


def _run_combo(args) -> tuple[str, str, dict]:
    """One (day, train set): build the network once, then every origin for both profiles."""
    day_type, train_set, tt, stations, transfer_minutes, only = args
    net = network.build(tt, train_set)
    out: dict[str, dict] = {}
    for prof_name in PROFILES:
        prof = network.profile(net, prof_name, stations, transfer_minutes)
        for code in net.station_codes:
            if only and code not in only:
                continue
            out.setdefault(code, {})[prof_name] = origin_results(net, prof, code)
    return day_type, train_set, out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--today", help="pretend today is YYYY-MM-DD (for reproducible builds)")
    ap.add_argument("--only", nargs="*", help="only these origin codes (quick runs)")
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    args = ap.parse_args(argv)
    started = time.time()
    today = date.fromisoformat(args.today) if args.today else date.today()

    gtfs.ensure_feed()
    info = gtfs.feed_info()
    trips, dates = gtfs.rail_trips(), gtfs.service_dates()
    days = gtfs.choose_days(trips, dates, today)
    iff = gtfs.iff_stations()
    nl_codes = set(iff.filter(pl.col("country") == "NL")["code"])
    transfer_minutes = dict(zip(iff["code"], iff["transfer_min"]))
    stations = access.load()
    timetables = {d: gtfs.day_timetable(days[d], trips, dates, nl_codes) for d in DAY_TYPES}
    print(f"days: {days}; EPIAP {next(iter(stations.values())).source_date}; loading took {time.time() - started:.0f}s")

    combos = [(d, s, timetables[d], stations, transfer_minutes, set(args.only or [])) for d in DAY_TYPES for s in TRAIN_SETS]
    results: dict[str, dict] = {}
    # "spawn", not Linux's default "fork": a forked child inherits polars' thread pool mid-use
    # and can deadlock (the first CI build hung). Windows always spawns.
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn")) as pool:
        for day_type, train_set, out in pool.map(_run_combo, combos):
            for code, per_profile in out.items():
                for prof_name, dests in per_profile.items():
                    results.setdefault(code, {}).setdefault(day_type, {}).setdefault(prof_name, {})[train_set] = dests
            print(f"  {day_type}/{train_set} done ({time.time() - started:.0f}s)")
    check_router(results)
    for per_day in results.values():
        for day_results in per_day.values():
            more_options_never_worse(day_results)

    served = sorted({c for tt in timetables.values() for c in tt.stations["code"]})
    coords = pl.concat([tt.stations for tt in timetables.values()]).unique("code").sort("code")
    tmp = BUILD.with_name("build.tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "origins").mkdir(parents=True)

    trains_per_day = dict(timetables["weekday"].stop_times.group_by("station").len().iter_rows())
    iff_names = dict(zip(iff["code"], iff["iff_name"]))
    station_rows = []
    for row in coords.iter_rows(named=True):
        st = stations.get(row["code"])
        name = st.name if st else row["name"]
        aliases = sorted({n for n in (row["name"], iff_names.get(row["code"])) if n and n != name})
        station_rows.append({
            "code": row["code"],
            "name": name,
            "aliases": aliases,
            "trains": trains_per_day.get(row["code"], 0),
            "lat": round(row["lat"], 5),
            "lon": round(row["lon"], 5),
            "status": st.status if st else "unknown",
            "tracks": dict(sorted((t, v) for t, v in st.tracks.items() if t in st.main_tracks)) if st else {},
            "source": st.source if st else "none",
            "source_date": st.source_date if st else None,
            "verified": st.verified if st else None,
            "notes": st.notes if st else [],
            "uic": st.uic if st else None,
            "lifts": [{"id": lf["id"], "code": lf["code"], "tracks": lf["tracks"]} for lf in st.lifts] if st else [],
        })
    slugs = unique_slugs({r["code"]: r["name"] for r in station_rows})
    for r in station_rows:
        r["slug"] = slugs[r["code"]]  # the station page: /station/<slug>/
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for code in served:
        doc = {"v": FORMAT_VERSION, "origin": code, "built": built_at, "results": results.get(code, {})}
        (tmp / "origins" / f"{code}.json").write_text(json.dumps(doc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    (tmp / "stations.json").write_text(json.dumps(station_rows, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    meta = {
        "v": FORMAT_VERSION,
        "built": built_at,
        "days": {k: v.isoformat() for k, v in days.items()},
        "window": [config.WINDOW_START, config.WINDOW_END],
        "max_changes": config.MAX_TRANSFERS,
        "stroller_buffer_min": config.STROLLER_BUFFER,
        "train_sets": {"all": f"all trains except {sorted(config.EXCLUDED_CATEGORIES)}",
                       "sprinter": "NS Sprinters and all regional/cross-border stopping trains; no NS Intercity or international"},
        "gtfs": {"version": info["feed_version"], "valid": [info["feed_start_date"], info["feed_end_date"]]},
        "epiap_date": next(iter(stations.values())).source_date,
        "inputs": inputs.fingerprint(),  # lets the nightly job skip a build when nothing changed
        "entry_format": "[median_min, fastest_min, departures_per_hour, changes, 'VIA|VIA'?] per change limit 0,1,2; "
                        "missing trailing entries = same as the last one; null = no journey; each entry is the best "
                        "(shortest median) of its own and those with fewer options (changes, intercities, no pram)",
        "sources": [
            {"name": "Dienstregeling (GTFS)", "by": "OVapi / Stichting OpenGeo", "url": "http://gtfs.ovapi.nl/"},
            {"name": "Toegankelijkheid stations (NeTEx EPIAP)", "by": "DOVA / ProRail via NDOV Loket", "licence": "CC0",
             "url": "https://data.ndovloket.nl/netex/epiap/"},
            {"name": "Overstaptijden (IFF)", "by": "NS via NDOV Loket", "licence": "CC0", "url": "https://data.ndovloket.nl/ns/"},
        ],
        "counts": {"stations": len(station_rows), "origins": len(served)},
    }
    (tmp / "meta.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")

    validate(tmp, partial=bool(args.only))
    if BUILD.exists():
        shutil.rmtree(BUILD)
    tmp.rename(BUILD)
    size = sum(f.stat().st_size for f in BUILD.rglob("*") if f.is_file())
    print(f"built {len(served)} origins, {size / 1e6:.1f} MB, in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
