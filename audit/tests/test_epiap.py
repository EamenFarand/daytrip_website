"""Parser tests on a trimmed copy of the real EPIAP entry for Houten (2026-09-29)."""

import gzip
from pathlib import Path

import polars as pl

import build_stations
import epiap

HOUTEN = """<?xml version="1.0" encoding="UTF-8"?>
<PublicationDelivery xmlns="http://www.netex.org.uk/netex" xmlns:gml="http://www.opengis.net/gml/3.2">
 <dataObjects><CompositeFrame><frames><SiteFrame><stopPlaces>
  <StopPlace id="NL:CHB:StopPlace:8400340">
   <privateCodes><PrivateCode type="StopPlaceCode">NL:S:htn</PrivateCode></privateCodes>
   <Name>Houten</Name>
   <Centroid><Location><gml:pos>139968 449541</gml:pos></Location></Centroid>
   <AccessibilityAssessment><MobilityImpairedAccess>true</MobilityImpairedAccess></AccessibilityAssessment>
   <placeEquipments>
    <LiftEquipment id="NL:CHB:LiftEquipment:8400340_001">
     <PublicCode>HTN-LIF-001</PublicCode><Description>HTN-LIF-001 Spoor 1/2</Description><Monitored>true</Monitored>
    </LiftEquipment>
   </placeEquipments>
   <TransportMode>rail</TransportMode>
   <quays>
    <Quay id="NL:CHB:Quay:8400340_1">
     <AccessibilityAssessment><MobilityImpairedAccess>true</MobilityImpairedAccess><limitations><AccessibilityLimitation>
      <WheelchairAccess>true</WheelchairAccess><StepFreeAccess>true</StepFreeAccess>
     </AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>1</PublicCode><QuayType>railPlatform</QuayType><ParentQuayRef ref="NL:CHB:Quay:8400340_1n2"/>
    </Quay>
    <Quay id="NL:CHB:Quay:8400340_2">
     <AccessibilityAssessment><MobilityImpairedAccess>true</MobilityImpairedAccess><limitations><AccessibilityLimitation>
      <WheelchairAccess>true</WheelchairAccess><StepFreeAccess>unknown</StepFreeAccess>
     </AccessibilityLimitation></limitations></AccessibilityAssessment>
     <PublicCode>2</PublicCode><QuayType>railPlatform</QuayType><ParentQuayRef ref="NL:CHB:Quay:8400340_1n2"/>
    </Quay>
    <Quay id="NL:CHB:Quay:8400340_1n2">
     <equipmentPlaces><EquipmentPlace id="NL:CHB:EquipmentPlace:8400340_LEq_001_Q_1n2">
      <placeEquipments><LiftEquipmentRef ref="NL:CHB:LiftEquipment:8400340_001"/></placeEquipments>
     </EquipmentPlace></equipmentPlaces>
     <PublicCode>1-2</PublicCode><QuayType>railIslandPlatform</QuayType>
    </Quay>
   </quays>
  </StopPlace>
  <StopPlace id="NL:CHB:StopPlace:1234"><Name>Bus stop</Name><TransportMode>bus</TransportMode></StopPlace>
 </stopPlaces></SiteFrame></frames></CompositeFrame></dataObjects>
</PublicationDelivery>
"""


def parse(tmp_path: Path):
    path = tmp_path / "epiap.xml.gz"
    path.write_bytes(gzip.compress(HOUTEN.encode()))
    return epiap.parse(path)


def test_only_rail_stations_are_kept(tmp_path):
    stations, _, _ = parse(tmp_path)
    assert [s["ns_code"] for s in stations] == ["HTN"]
    assert stations[0]["uic"] == "8400340"


def test_island_container_is_not_counted_as_a_track(tmp_path):
    stations, quays, _ = parse(tmp_path)
    s = stations[0]
    assert len(quays) == 3
    assert (s["n_quays"], s["n_quays_stepfree_true"], s["n_quays_stepfree_unknown"]) == (2, 1, 1)


def test_lift_on_island_platform_serves_both_tracks(tmp_path):
    _, _, lifts = parse(tmp_path)
    assert lifts[0]["public_code"] == "HTN-LIF-001"
    assert lifts[0]["serves_tracks"] == "1|2"


def test_status_is_conservative():
    df = pl.DataFrame({"t": [2, 1, 0, 0, 0], "f": [0, 0, 2, 0, 1], "n": [2, 2, 2, 2, 2]})
    out = df.select(build_stations.status_from_counts(pl.col("t"), pl.col("f"), pl.col("n")))
    # one unknown track keeps a station from being "yes"; no tracks at all is "unknown"
    assert out.to_series().to_list() == ["yes", "partial", "no", "unknown", "unknown"]
