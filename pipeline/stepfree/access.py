"""Step-free status per station and platform track.

Source: DOVA NeTEx EPIAP export on NDOV Loket (CC0), refreshed daily, one
`StepFreeAccess` value per platform track. Then a hand-kept overrides file
(pipeline/overrides/stations.csv) for anomalies and in-person checks.

Status values: "yes", "no", "unknown". Unknown counts as not step-free.

EPIAP quay types:
  railPlatform        one track side, e.g. "5"      -> a track
  railIslandPlatform  container for two tracks "4-5" -> a shared platform surface
  railPlatformSector  part of a track, e.g. "5a"    -> looked up like its track
"""

from __future__ import annotations

import csv
import gzip
import re
from dataclasses import dataclass, field

from lxml import etree

from .config import EPIAP_DIR, OVERRIDES
from .fetch import fetch, latest_listed

N = "{http://www.netex.org.uk/netex}"
STATUS = {"true": "yes", "false": "no"}


@dataclass
class Station:
    code: str
    uic: str
    name: str
    tracks: dict[str, str] = field(default_factory=dict)  # track/sector code -> status
    islands: dict[str, list[str]] = field(default_factory=dict)  # "4-5" -> ["4", "5"]
    surface: dict[str, str] = field(default_factory=dict)  # track/sector/island code -> surface id
    main_tracks: list[str] = field(default_factory=list)  # codes that count for the station status
    lifts: list[dict] = field(default_factory=list)
    source: str = "EPIAP"
    source_date: str = ""
    verified: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        """Station level: "yes" only if every track is, "partial" if some are."""
        values = [self.tracks[t] for t in self.main_tracks]
        if not values:
            return "unknown"
        if all(v == "yes" for v in values):
            return "yes"
        if any(v == "yes" for v in values):
            return "partial"
        if all(v == "no" for v in values):
            return "no"
        return "unknown"

    def _key(self, platform: str) -> str | None:
        p = platform.lower()
        if p in self.tracks or p in self.islands:
            return p
        base = re.sub(r"[a-z]$", "", p)  # GTFS "5b" when EPIAP only has "5"
        if base in self.tracks or base in self.islands:
            return base
        return None

    def knows(self, platform: str) -> bool:
        return self._key(platform) is not None

    def platform_status(self, platform: str) -> str:
        key = self._key(platform)
        if key is None:
            return "unknown"
        if key in self.islands:  # GTFS sometimes names the island ("1-2") instead of the track
            values = {self.tracks.get(t, "unknown") for t in self.islands[key]}
            return values.pop() if len(values) == 1 else "unknown"
        return self.tracks[key]

    def platform_surface(self, platform: str) -> str:
        key = self._key(platform)
        return self.surface.get(key, f"?{platform.lower()}") if key else f"?{platform.lower()}"


def _step_free(quay) -> str:
    path = f"{N}AccessibilityAssessment/{N}limitations/{N}AccessibilityLimitation/{N}StepFreeAccess"
    return STATUS.get(quay.findtext(path) or "", "unknown")


def _code(quay) -> str:
    return (quay.findtext(N + "PublicCode") or quay.get("id").rsplit("_", 1)[-1]).lower()


def parse_epiap(path, epiap_date: str) -> dict[str, Station]:
    stations: dict[str, Station] = {}
    for _, sp in etree.iterparse(gzip.open(path), events=("end",), tag=N + "StopPlace"):
        if sp.findtext(N + "TransportMode") != "rail":
            sp.clear()
            continue
        code = (sp.findtext(f"{N}privateCodes/{N}PrivateCode") or "").removeprefix("NL:S:").upper()
        st = Station(code=code, uic=sp.get("id").rsplit(":", 1)[-1], name=sp.findtext(N + "Name") or code,
                     source_date=epiap_date)
        quays = list(sp.iterfind(f"{N}quays/{N}Quay"))
        by_id = {q.get("id"): q for q in quays}
        parent_of = {}
        for q in quays:
            ref = q.find(N + "ParentQuayRef")
            if ref is not None and ref.get("ref") in by_id:
                parent_of[q.get("id")] = by_id[ref.get("ref")]

        def island_of(q):
            """The island platform a quay stands on, following sector -> track -> island."""
            while q is not None:
                if q.findtext(N + "QuayType") == "railIslandPlatform":
                    return q
                q = parent_of.get(q.get("id"))
            return None

        for q in quays:
            qtype, c = q.findtext(N + "QuayType"), _code(q)
            island = island_of(q)
            if qtype == "railIslandPlatform":
                st.islands.setdefault(c, [])  # its tracks may already have registered themselves
                st.surface[c] = q.get("id")
                continue
            st.tracks[c] = _step_free(q)
            if island is not None:
                st.surface[c] = island.get("id")
                if qtype == "railPlatform":
                    st.islands.setdefault(_code(island), []).append(c)
            else:
                track = parent_of.get(q.get("id"))  # a sector's own track, if any
                st.surface[c] = track.get("id") if track is not None else q.get("id")
            if qtype == "railPlatform" or (qtype == "railPlatformSector" and q.get("id") not in parent_of):
                st.main_tracks.append(c)

        for le in sp.iter(N + "LiftEquipment"):
            served: set[str] = set()
            for q in quays:
                if any(r.get("ref") == le.get("id") for r in q.iter(N + "LiftEquipmentRef")):
                    c = _code(q)
                    served.update(st.islands.get(c) or [c])
            st.lifts.append({"id": le.get("id").rsplit(":", 1)[-1], "code": le.findtext(N + "PublicCode"),
                             "description": le.findtext(N + "Description"), "tracks": sorted(served)})
        stations[code] = st
        sp.clear()
    return stations


def apply_overrides(stations: dict[str, Station], path=OVERRIDES) -> None:
    """Apply pipeline/overrides/stations.csv: one row per station (blank track) or per track."""
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            st = stations.get(row["ns_code"])
            if st is None:
                raise ValueError(f"override for a station not in EPIAP: {row['ns_code']}")
            if row["status"] not in ("yes", "no", "unknown"):
                raise ValueError(f"bad status in override: {row}")
            track = row["track"].strip().lower()
            if track and track not in st.tracks:
                raise ValueError(f"override for unknown track {row['ns_code']} {track}")
            for t in [track] if track else list(st.tracks):
                st.tracks[t] = row["status"]
            if row["source"].startswith("in person") and row["status"] == "yes" and not track:
                st.verified = f"{row['source']}, {row['date']}"
            else:
                st.source = "EPIAP + correction"
            st.notes.append(f"{row['reason']} ({row['source']}, {row['date']})")


def load() -> dict[str, Station]:
    url = latest_listed(EPIAP_DIR, r"NeTEx_DOVA_epiap_\d{4}-\d{2}-\d{2}\.xml\.gz")
    epiap_date = re.search(r"(\d{4}-\d{2}-\d{2})", url).group(1)
    stations = parse_epiap(fetch(url, "netex/epiap.xml.gz"), epiap_date)
    apply_overrides(stations)
    return stations
