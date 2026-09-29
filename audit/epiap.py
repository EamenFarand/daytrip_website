"""Q3 + Q4: parse the DOVA NeTEx EPIAP export (station accessibility, CC0).

Source: https://data.ndovloket.nl/netex/epiap/ (daily, one file per day).
The file is the Centraal Haltebestand (CHB) exported in the NeTEx European
Passenger Information Accessibility Profile. Rail stations carry per-platform
(Quay) accessibility flags plus a topology of levels, entrances, lifts,
ramps and path links.

Outputs (data/raw/derived/):
  epiap_rail_stations.parquet  one row per rail StopPlace
  epiap_rail_quays.parquet     one row per platform track (Quay)
  epiap_lifts.parquet          one row per LiftEquipment at a rail StopPlace
"""

from __future__ import annotations

import gzip
import re

import polars as pl
import requests
from lxml import etree

from fetch import RAW, USER_AGENT, fetch

BASE = "https://data.ndovloket.nl/netex/epiap/"
N = "{http://www.netex.org.uk/netex}"
DERIVED = RAW / "derived"
LIMITS = ["WheelchairAccess", "StepFreeAccess", "LiftFreeAccess", "RampFreeAccess", "LevelAccessIntoVehicle"]


def latest_url() -> str:
    """The directory holds one dated file; find it instead of guessing the date."""
    html = requests.get(BASE, headers={"User-Agent": USER_AGENT}, timeout=60).text
    names = sorted(set(re.findall(r'href="(NeTEx_DOVA_epiap_\d{4}-\d{2}-\d{2}\.xml\.gz)"', html)))
    if not names:
        raise RuntimeError(f"no EPIAP file listed at {BASE}")
    return BASE + names[-1]


def assessment(el) -> dict[str, str | None]:
    aa = el.find(N + "AccessibilityAssessment")
    out: dict[str, str | None] = {"mobility_impaired_access": None}
    out.update({k: None for k in LIMITS})
    if aa is None:
        return out
    out["mobility_impaired_access"] = aa.findtext(N + "MobilityImpairedAccess")
    lim = aa.find(f"{N}limitations/{N}AccessibilityLimitation")
    if lim is not None:
        for k in LIMITS:
            out[k] = lim.findtext(N + k)
    return out


def parse(path) -> tuple[list[dict], list[dict], list[dict]]:
    stations, quays, lifts = [], [], []
    for _, sp in etree.iterparse(gzip.open(path), events=("end",), tag=N + "StopPlace"):
        if sp.findtext(N + "TransportMode") != "rail":
            sp.clear()
            continue
        sp_id = sp.get("id")
        uic = sp_id.rsplit(":", 1)[-1]
        code = sp.findtext(f"{N}privateCodes/{N}PrivateCode") or ""
        ns_code = code.removeprefix("NL:S:").upper() if code.startswith("NL:S:") else None
        pos = (sp.findtext(f"{N}Centroid/{N}Location/{{http://www.opengis.net/gml/3.2}}pos") or "").split()
        x, y = pos[:2] if len(pos) >= 2 else (None, None)
        st = assessment(sp)

        # Quay types: railPlatform = one track side (what trains stop at),
        # railIslandPlatform = container for two tracks, railPlatformSector = part of a track (4a/4b).
        # Station-level counts use tracks only. A sector without a parent track
        # (Daarlerveen: 1a/1b) stands in for the track.
        platform_quays = []
        lift_quays: dict[str, set[str]] = {}
        for q in sp.iterfind(f"{N}quays/{N}Quay"):
            qa = assessment(q)
            qtype = q.findtext(N + "QuayType")
            parent = q.find(N + "ParentQuayRef")
            row = {
                "uic": uic,
                "ns_code": ns_code,
                "quay_id": q.get("id"),
                "quay_code": q.findtext(f"{N}privateCodes/{N}PrivateCode"),
                "public_code": q.findtext(N + "PublicCode"),
                "quay_type": qtype,
                "parent_quay": parent.get("ref") if parent is not None else None,
                "n_lift_refs": len(q.findall(f".//{N}LiftEquipmentRef")),
                "n_ramp_refs": len(q.findall(f".//{N}RampEquipmentRef")),
                **{("quay_" + k if k == "mobility_impaired_access" else k): v for k, v in qa.items()},
            }
            quays.append(row)
            for ref in q.iter(N + "LiftEquipmentRef"):
                lift_quays.setdefault(ref.get("ref"), set()).add(row["quay_id"])
            if qtype == "railPlatform" or (qtype == "railPlatformSector" and parent is None):
                platform_quays.append(row)

        # a lift that serves an island platform serves both of its tracks
        children: dict[str, list[str]] = {}
        for row in quays:
            if row["uic"] == uic and row["parent_quay"] and row["quay_type"] == "railPlatform":
                children.setdefault(row["parent_quay"], []).append(row["public_code"])
        codes = {row["quay_id"]: row["public_code"] for row in quays if row["uic"] == uic}

        for le in sp.iterfind(f".//{N}LiftEquipment"):
            served: set[str] = set()
            for qid in lift_quays.get(le.get("id"), ()):
                served.update(children.get(qid, [codes.get(qid)]))
            lifts.append(
                {
                    "uic": uic,
                    "ns_code": ns_code,
                    "lift_id": le.get("id"),
                    "public_code": le.findtext(N + "PublicCode"),
                    "description": le.findtext(N + "Description"),
                    "monitored": le.findtext(N + "Monitored"),
                    "serves_tracks": "|".join(sorted(s for s in served if s)),
                }
            )

        sf = [q["StepFreeAccess"] for q in platform_quays]
        stations.append(
            {
                "uic": uic,
                "ns_code": ns_code,
                "epiap_name": sp.findtext(N + "Name"),
                "rd_x": float(x) if x else None,
                "rd_y": float(y) if y else None,
                "station_mobility_impaired_access": st["mobility_impaired_access"],
                "n_quays": len(platform_quays),
                "n_quays_stepfree_true": sf.count("true"),
                "n_quays_stepfree_false": sf.count("false"),
                "n_quays_stepfree_unknown": len(sf) - sf.count("true") - sf.count("false"),
                "n_levels": len(sp.findall(f"{N}levels/{N}Level")),
                "n_entrances": len(sp.findall(f"{N}entrances/{N}StopPlaceEntrance")),
                "n_lifts": len(sp.findall(f".//{N}LiftEquipment")),
                "n_ramps": len(sp.findall(f".//{N}RampEquipment")),
                "n_escalators": len(sp.findall(f".//{N}EscalatorEquipment")),
                "n_path_links": len(sp.findall(f"{N}pathLinks/{N}SitePathLink")),
                "n_access_spaces": len(sp.findall(f".//{N}AccessSpace")),
            }
        )
        sp.clear()
    return stations, quays, lifts


def main() -> None:
    url = latest_url()
    path = fetch(url, "netex/epiap.xml.gz")
    stations, quays, lifts = parse(path)
    DERIVED.mkdir(parents=True, exist_ok=True)
    feed_date = re.search(r"(\d{4}-\d{2}-\d{2})", url).group(1)
    pl.DataFrame(stations).with_columns(pl.lit(feed_date).alias("epiap_date")).write_parquet(DERIVED / "epiap_rail_stations.parquet")
    pl.DataFrame(quays).write_parquet(DERIVED / "epiap_rail_quays.parquet")
    pl.DataFrame(lifts).write_parquet(DERIVED / "epiap_lifts.parquet")
    print(f"EPIAP {feed_date}: {len(stations)} rail stations, {len(quays)} quays, {len(lifts)} lifts")


if __name__ == "__main__":
    main()
