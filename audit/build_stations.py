"""Q1 + Q3 + Q6: build the master station table, audit/stations.csv.

One row per Dutch rail station served by a train in the current GTFS feed.
Key: NS station code (upper case). Every source is joined on that code,
except ProRail's boarding file, which only has names.

Per-source step-free status is normalised to: yes / no / partial / unknown.
Run the source scripts first (see audit/README.md), or just `run_all.py`.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path

import polars as pl

from fetch import RAW

DERIVED = RAW / "derived"
OUT = Path(__file__).resolve().parent / "stations.csv"


def norm_name(col: pl.Expr) -> pl.Expr:
    return (
        col.map_elements(
            lambda s: unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode() if s else s,
            return_dtype=pl.String,
        )
        .str.to_lowercase()
        .str.replace_all(r"[^a-z0-9]+", " ")
        .str.strip_chars()
    )


def status_from_counts(true: pl.Expr, false: pl.Expr, total: pl.Expr) -> pl.Expr:
    return (
        pl.when(total.is_null() | (total == 0))
        .then(pl.lit("unknown"))
        .when(true == total)
        .then(pl.lit("yes"))
        .when(false == total)
        .then(pl.lit("no"))
        .when(true == 0)
        .then(pl.lit("unknown"))
        .otherwise(pl.lit("partial"))
    )


def main() -> None:
    gtfs = pl.read_parquet(DERIVED / "gtfs_rail_stations.parquet").filter(pl.col("gtfs_parent_id").is_not_null())
    plat = pl.read_parquet(DERIVED / "gtfs_rail_platforms.parquet")
    iff = pl.read_parquet(DERIVED / "iff_stations.parquet")
    epiap = pl.read_parquet(DERIVED / "epiap_rail_stations.parquet")
    pr20 = pl.read_parquet(DERIVED / "prorail_2020_stepfree.parquet")
    board = pl.read_parquet(DERIVED / "prorail_boarding.parquet")
    osm = pl.read_parquet(DERIVED / "osm_rail_stations.parquet")
    assets = pl.read_parquet(DERIVED / "prorail_assets.parquet")
    topo = pl.read_parquet(DERIVED / "epiap_topology.parquet").select("ns_code", "topology_via_halls")
    quays = pl.read_parquet(DERIVED / "epiap_rail_quays.parquet")

    # Two tracks on one island platform should share a step-free value; flag where they don't.
    island_conflicts = (
        quays.filter(pl.col("parent_quay").is_not_null() & (pl.col("quay_type") == "railPlatform"))
        .group_by("ns_code", "parent_quay")
        .agg(pl.col("StepFreeAccess").n_unique().alias("n"))
        .filter(pl.col("n") > 1)
        .select("ns_code", pl.lit(True).alias("island_conflict"))
        .unique()
    )

    # GTFS: wheelchair_boarding per platform stop (1 = accessible, empty = no info)
    wb = plat.group_by("parent_station").agg(
        (pl.col("wheelchair_boarding") == "1").sum().alias("gtfs_wb_1"),
        (pl.col("wheelchair_boarding") == "2").sum().alias("gtfs_wb_2"),
        pl.len().alias("gtfs_wb_total"),
    )
    base = (
        gtfs.rename({"iff_code": "ns_code"})
        .join(wb, left_on="gtfs_parent_id", right_on="parent_station", how="left")
        .join(iff, on="ns_code", how="left")
        .filter(pl.col("iff_country") == "NL")
        .with_columns(status_from_counts(pl.col("gtfs_wb_1"), pl.col("gtfs_wb_2"), pl.col("gtfs_wb_total")).alias("gtfs_wb_status"))
    )

    epiap = epiap.with_columns(
        status_from_counts(
            pl.col("n_quays_stepfree_true"), pl.col("n_quays_stepfree_false"), pl.col("n_quays")
        ).alias("epiap_status")
    ).select(
        "ns_code",
        "uic",
        "epiap_name",
        "epiap_status",
        pl.col("station_mobility_impaired_access").alias("epiap_station_access"),
        pl.col("n_quays").alias("epiap_quays"),
        pl.col("n_quays_stepfree_true").alias("epiap_quays_sf_true"),
        pl.col("n_quays_stepfree_false").alias("epiap_quays_sf_false"),
        pl.col("n_quays_stepfree_unknown").alias("epiap_quays_sf_unknown"),
        pl.col("n_lifts").alias("epiap_lifts"),
        pl.col("n_ramps").alias("epiap_ramps"),
        pl.col("n_path_links").alias("epiap_path_links"),
        "epiap_date",
    )

    osm1 = (
        osm.filter(pl.col("osm_ns_code").is_not_null())
        .sort("osm_wheelchair", nulls_last=True)
        .group_by("osm_ns_code")
        .agg(
            pl.col("osm_wheelchair").first(),
            pl.col("osm_elevators_250m").max(),
            pl.col("osm_uic").drop_nulls().first(),
            pl.len().alias("osm_objects"),
        )
        .rename({"osm_ns_code": "ns_code"})
        .with_columns(
            pl.col("osm_wheelchair")
            .replace_strict({"yes": "yes", "no": "no", "limited": "partial"}, default="unknown")
            .alias("osm_status")
        )
    )

    t = (
        base.join(epiap, on="ns_code", how="left")
        .join(pr20, on="ns_code", how="left")
        .join(osm1, on="ns_code", how="left")
        .join(assets, on="ns_code", how="left")
        .join(topo, on="ns_code", how="left")
        .join(island_conflicts, on="ns_code", how="left")
        .with_columns(
            pl.col("epiap_status").fill_null("unknown"),
            pl.col("osm_status").fill_null("unknown"),
            pl.col("pr2020_reachable").fill_null("unknown").alias("pr2020_status"),
            pl.when(pl.col("ns_tgst")).then(pl.lit("yes")).otherwise(pl.lit("no")).alias("ns_tgst_status"),
            norm_name(pl.col("gtfs_name")).alias("_n1"),
            norm_name(pl.col("iff_name")).alias("_n2"),
            norm_name(pl.col("epiap_name")).alias("_n3"),
        )
    )

    # ProRail boarding file has names only: try GTFS, IFF, then EPIAP names.
    board = board.with_columns(norm_name(pl.col("pr_board_name")).alias("_nb"))
    matched = None
    for key in ["_n1", "_n2", "_n3"]:
        m = t.select("ns_code", key).join(board, left_on=key, right_on="_nb", how="inner").drop(key)
        matched = m if matched is None else pl.concat([matched, m.filter(~pl.col("ns_code").is_in(matched["ns_code"].implode()))])
    t = t.join(matched.unique("ns_code"), on="ns_code", how="left").with_columns(
        pl.when(pl.col("pr_board_tracks").is_null())
        .then(pl.lit("unknown"))
        .when(pl.col("pr_board_tracks_ok") == pl.col("pr_board_tracks"))
        .then(pl.lit("yes"))
        .when(pl.col("pr_board_tracks_ok") == 0)
        .then(pl.lit("no"))
        .otherwise(pl.lit("partial"))
        .alias("pr_boarding_status")
    )

    # Recommended status: EPIAP, made more conservative where evidence conflicts.
    conflict = (pl.col("epiap_status") == "yes") & ((pl.col("pr2020_status") == "no") | (pl.col("osm_status") == "no"))
    no_equipment = (
        (pl.col("epiap_lifts").fill_null(0) == 0)
        & (pl.col("epiap_ramps").fill_null(0) == 0)
        & (pl.col("reg_lifts").fill_null(0) == 0)
        & (pl.col("reg_ramps").fill_null(0) == 0)
    )
    lift_in_project = pl.col("reg_lift_status").fill_null("").str.contains("PROJ") & ~pl.col(
        "reg_lift_status"
    ).fill_null("").str.contains("VRIJ")
    t = t.with_columns(
        pl.when(conflict & no_equipment)
        .then(pl.lit("other source says no; no lift or ramp in EPIAP or ProRail register"))
        .when(conflict & lift_in_project)
        .then(pl.lit("other source says no; ProRail register lists the lift as a project"))
        .when(conflict)
        .then(pl.lit("other source says no; lifts/ramps present, likely upgraded since"))
        .when(pl.col("island_conflict").fill_null(False))
        .then(pl.lit("tracks on one island platform disagree"))
        .otherwise(pl.lit(None))
        .alias("review_reason"),
    ).with_columns(
        pl.when(conflict & (no_equipment | lift_in_project))
        .then(pl.lit("unknown"))
        .otherwise(pl.col("epiap_status"))
        .alias("recommended_status")
    )

    cols = [
        "ns_code", "uic", "gtfs_name", "lat", "lon", "operators", "n_trips", "gtfs_parent_id", "n_platform_stops",
        "iff_transfer_minutes",
        # outcome
        "recommended_status", "review_reason",
        # step-free status per source
        "epiap_status", "epiap_station_access", "epiap_quays", "epiap_quays_sf_true", "epiap_quays_sf_false",
        "epiap_quays_sf_unknown", "epiap_lifts", "epiap_ramps", "epiap_path_links", "topology_via_halls", "epiap_date",
        "reg_lifts", "reg_lift_status", "reg_ramps",
        "gtfs_wb_status", "gtfs_wb_1", "gtfs_wb_total",
        "ns_tgst_status", "ns_rast",
        "pr2020_status", "pr2020_category", "pr2020_date", "pr2020_note",
        "osm_status", "osm_wheelchair", "osm_elevators_250m", "osm_objects",
        # not step-free access, but related: platform height for level boarding
        "pr_boarding_status", "pr_board_tracks", "pr_board_tracks_ok", "pr_board_statuses",
    ]
    t = t.select(cols).sort("gtfs_name")
    t.write_csv(OUT)
    print(f"wrote {OUT.name}: {t.height} stations")


if __name__ == "__main__":
    main()
