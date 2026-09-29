"""EPIAP parsing, platform lookups, overrides and the sprinter rule."""

import gzip

import pytest

from stepfree import access
from stepfree.config import in_train_set

# One station: island platform 1-2 with a lift, side platform 3 split into sectors 3a/3b.
EPIAP = """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex" xmlns:gml="http://www.opengis.net/gml/3.2">
 <dataObjects><CompositeFrame><frames><SiteFrame><stopPlaces>
  <StopPlace id="NL:CHB:StopPlace:8400999">
   <privateCodes><PrivateCode>NL:S:tst</PrivateCode></privateCodes>
   <Name>Teststad</Name>
   <placeEquipments><LiftEquipment id="NL:CHB:LiftEquipment:8400999_001"><PublicCode>TST-LIF-001</PublicCode></LiftEquipment></placeEquipments>
   <TransportMode>rail</TransportMode>
   <quays>
    <Quay id="Q1"><AccessibilityAssessment><limitations><AccessibilityLimitation><StepFreeAccess>true</StepFreeAccess></AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>1</PublicCode><QuayType>railPlatform</QuayType><ParentQuayRef ref="Q1n2"/></Quay>
    <Quay id="Q2"><AccessibilityAssessment><limitations><AccessibilityLimitation><StepFreeAccess>true</StepFreeAccess></AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>2</PublicCode><QuayType>railPlatform</QuayType><ParentQuayRef ref="Q1n2"/></Quay>
    <Quay id="Q1n2"><equipmentPlaces><EquipmentPlace id="E1"><placeEquipments><LiftEquipmentRef ref="NL:CHB:LiftEquipment:8400999_001"/></placeEquipments></EquipmentPlace></equipmentPlaces>
     <PublicCode>1-2</PublicCode><QuayType>railIslandPlatform</QuayType></Quay>
    <Quay id="Q3"><AccessibilityAssessment><limitations><AccessibilityLimitation><StepFreeAccess>false</StepFreeAccess></AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>3</PublicCode><QuayType>railPlatform</QuayType></Quay>
    <Quay id="Q3b"><AccessibilityAssessment><limitations><AccessibilityLimitation><StepFreeAccess>false</StepFreeAccess></AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>3b</PublicCode><QuayType>railPlatformSector</QuayType><ParentQuayRef ref="Q3"/></Quay>
   </quays>
  </StopPlace>
 </stopPlaces></SiteFrame></frames></CompositeFrame></dataObjects>
</PublicationDelivery>"""


@pytest.fixture
def stations(tmp_path):
    path = tmp_path / "epiap.xml.gz"
    path.write_bytes(gzip.compress(EPIAP.encode()))
    return access.parse_epiap(path, "2026-09-29")


def test_tracks_islands_and_station_status(stations):
    st = stations["TST"]
    assert st.main_tracks == ["1", "2", "3"]  # the island and the sector don't count twice
    assert st.islands == {"1-2": ["1", "2"]}
    assert st.status == "partial"


def test_platform_lookup_handles_islands_sectors_and_missing_letters(stations):
    st = stations["TST"]
    assert st.platform_status("1-2") == "yes"  # GTFS sometimes names the island
    assert st.platform_status("3b") == "no"  # sector
    assert st.platform_status("3a") == "no"  # unknown sector falls back to its track
    assert st.platform_status("9") == "unknown"
    assert st.platform_surface("1") == st.platform_surface("2") != st.platform_surface("3")
    assert st.platform_surface("3b") == st.platform_surface("3")


def test_lift_on_island_serves_both_tracks(stations):
    assert stations["TST"].lifts == [{"id": "8400999_001", "code": "TST-LIF-001", "description": None, "tracks": ["1", "2"]}]


def test_overrides(stations, tmp_path):
    csv = tmp_path / "overrides.csv"
    csv.write_text(
        "ns_code,track,status,reason,source,date\n"
        "TST,3,yes,New ramp,in person (Daan),2026-10-01\n"
        "TST,,yes,Whole station checked,in person (Daan),2026-10-02\n",
        encoding="utf-8",
    )
    access.apply_overrides(stations, csv)
    st = stations["TST"]
    assert st.status == "yes"
    assert st.verified == "in person (Daan), 2026-10-02"
    assert len(st.notes) == 2


def test_override_for_unknown_track_fails_loudly(stations, tmp_path):
    csv = tmp_path / "overrides.csv"
    csv.write_text("ns_code,track,status,reason,source,date\nTST,7,no,x,y,2026-10-01\n", encoding="utf-8")
    with pytest.raises(ValueError):
        access.apply_overrides(stations, csv)


def test_real_overrides_file_matches_real_stations():
    """Every row in pipeline/overrides/stations.csv must name a station and track that exist."""
    from stepfree.config import CACHE

    path = CACHE / "netex" / "epiap.xml.gz"
    if not path.exists():
        pytest.skip("EPIAP not downloaded yet")
    stations = access.parse_epiap(path, "cached")
    access.apply_overrides(stations)  # raises on a typo


@pytest.mark.parametrize(
    "agency, category, sprinter",
    [
        ("NS", "Sprinter", True),
        ("NS", "Intercity", False),
        ("NS", "Intercity direct", False),
        ("NS International", "ICE", False),
        ("Arriva", "Sneltrein", True),
        ("Blauwnet Keolis", "Intercity", True),  # regional low-floor trains: option A
        ("R-net NS", "Sprinter", True),
    ],
)
def test_sprinter_rule(agency, category, sprinter):
    assert in_train_set(agency, category, "sprinter") is sprinter
    assert in_train_set(agency, category, "all") is True


@pytest.mark.parametrize("category", ["Drempelvrije bus", "Eurostar", "European Sleeper", "GoVolta", "Nightjet"])
def test_excluded_everywhere(category):
    assert not in_train_set("NS International", category, "all")
    assert not in_train_set("Miljoenenlijn", None, "all")
