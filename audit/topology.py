"""Q4: how usable is the EPIAP station topology for platform-to-platform routing?

For each rail station, build a graph from the NeTEx site elements:
  nodes  = entrances, quays, access spaces, equipment places
  edges  = SitePathLinks (both ways unless oneWay)
         + equipment place <-> the element it sits in
         + equipment places sharing the same lift or ramp (the lift/ramp joins them)
         + track quay <-> its parent island platform
Escalators do not count (not usable with a pram).

A platform is "topology-connected" when it can reach a StopPlaceEntrance in
that graph ("topology"), or an entrance or a hall/AccessSpace ("topology_via_halls",
because halls are often not linked to the street entrances). Stations with no path links at all are usually at ground level,
where the topology simply isn't modelled.

Output (data/raw/derived/): epiap_topology.parquet (one row per station)
"""

from __future__ import annotations

import gzip
from collections import defaultdict

import polars as pl
from lxml import etree

from fetch import RAW

N = "{http://www.netex.org.uk/netex}"
DERIVED = RAW / "derived"
CONTAINERS = {N + "StopPlaceEntrance", N + "Quay", N + "AccessSpace"}


def station_graph(sp) -> dict:
    adj: dict[str, set[str]] = defaultdict(set)

    def link(a: str, b: str) -> None:
        adj[a].add(b)
        adj[b].add(a)

    entrances = {e.get("id") for e in sp.iterfind(f"{N}entrances/{N}StopPlaceEntrance")}
    quays = {}
    for q in sp.iterfind(f"{N}quays/{N}Quay"):
        qid = q.get("id")
        parent = q.find(N + "ParentQuayRef")
        quays[qid] = {
            "type": q.findtext(N + "QuayType"),
            "parent": parent.get("ref") if parent is not None else None,
            "code": q.findtext(N + "PublicCode"),
        }
        if parent is not None:
            link(qid, parent.get("ref"))

    by_equipment: dict[str, list[str]] = defaultdict(list)
    for ep in sp.iter(N + "EquipmentPlace"):
        container = ep.getparent().getparent()
        if container.tag in CONTAINERS:
            link(ep.get("id"), container.get("id"))
        for ref in ep.iter(N + "LiftEquipmentRef", N + "RampEquipmentRef"):
            by_equipment[ref.get("ref")].append(ep.get("id"))
    for places in by_equipment.values():
        for other in places[1:]:
            link(places[0], other)

    n_links = 0
    for pl_ in sp.iterfind(f"{N}pathLinks/{N}SitePathLink"):
        n_links += 1
        a = pl_.find(f"{N}From/{N}PlaceRef")
        b = pl_.find(f"{N}To/{N}PlaceRef")
        if a is not None and b is not None:
            link(a.get("ref"), b.get("ref"))

    def reachable(roots: set[str]) -> set[str]:
        seen, stack = set(roots), list(roots)
        while stack:
            for nxt in adj[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    halls = {a.get("id") for a in sp.iter(N + "AccessSpace")}
    strict = reachable(entrances)
    loose = reachable(entrances | halls)  # halls often aren't linked to the street entrances
    tracks = [qid for qid, q in quays.items() if q["type"] == "railPlatform"]
    return {
        "n_entrances": len(entrances),
        "n_access_spaces": len(halls),
        "n_path_links": n_links,
        "n_tracks": len(tracks),
        "n_tracks_connected": sum(q in strict for q in tracks),
        "n_tracks_connected_via_hall": sum(q in loose for q in tracks),
        "unconnected_tracks": "|".join(sorted(quays[q]["code"] or q for q in tracks if q not in loose)),
    }


def main() -> None:
    rows = []
    for _, sp in etree.iterparse(gzip.open(RAW / "netex" / "epiap.xml.gz"), events=("end",), tag=N + "StopPlace"):
        if sp.findtext(N + "TransportMode") == "rail":
            code = sp.findtext(f"{N}privateCodes/{N}PrivateCode") or ""
            rows.append({"ns_code": code.removeprefix("NL:S:").upper(), "uic": sp.get("id").rsplit(":", 1)[-1], **station_graph(sp)})
        sp.clear()
    df = pl.DataFrame(rows).with_columns(
        pl.when(pl.col("n_path_links") == 0)
        .then(pl.lit("not modelled"))
        .when(pl.col("n_tracks_connected") == pl.col("n_tracks"))
        .then(pl.lit("all tracks connected"))
        .when(pl.col("n_tracks_connected") == 0)
        .then(pl.lit("no tracks connected"))
        .otherwise(pl.lit("some tracks connected"))
        .alias("topology"),
        pl.when(pl.col("n_path_links") == 0)
        .then(pl.lit("not modelled"))
        .when(pl.col("n_tracks_connected_via_hall") == pl.col("n_tracks"))
        .then(pl.lit("all tracks connected"))
        .when(pl.col("n_tracks_connected_via_hall") == 0)
        .then(pl.lit("no tracks connected"))
        .otherwise(pl.lit("some tracks connected"))
        .alias("topology_via_halls"),
    )
    df.write_parquet(DERIVED / "epiap_topology.parquet")
    print(df.group_by("topology", "topology_via_halls").len().sort("len", descending=True))


if __name__ == "__main__":
    main()
