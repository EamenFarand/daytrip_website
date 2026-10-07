"""Router behaviour on small hand-made networks.

Default network: two ways from O to D.
  fast: O -> X (change) -> D, arriving 10:30. X has no step-free route between its platforms.
  slow: O -> Y (change) -> D, arriving 10:50. Y is fully step-free.
"""

from stepfree import network, raptor
from stepfree.precompute import summarise

from toy import hm, station, timetable

FAST = {
    "T1": [("O", "1", "10:00", "10:00"), ("X", "1", "10:10", "10:10")],
    "T2": [("X", "2", "10:15", "10:15"), ("D", "1", "10:30", "10:30")],
}
SLOW = {
    "T3": [("O", "2", "10:00", "10:00"), ("Y", "1", "10:20", "10:20")],
    "T4": [("Y", "2", "10:30", "10:30"), ("D", "1", "10:50", "10:50")],
}
ACCESS = {
    "O": station("O", {"1": "yes", "2": "yes"}),
    "X": station("X", {"1": "no", "2": "no"}),
    "Y": station("Y", {"1": "yes", "2": "yes"}),
    "D": station("D", {"1": "yes"}),
}
MINUTES = {"O": 2, "X": 2, "Y": 2, "D": 2}


def search(trips, profile, access=ACCESS, transfers=(), origin="O", start="09:00", end="12:00", train_set="all",
           categories=None, minutes=MINUTES, step_free=None):
    tt = timetable(trips, transfers, categories)
    net = network.build(tt, train_set, step_free)
    prof = network.profile(net, profile, access, minutes)
    found = raptor.profile_search(net, prof, net.station_index[origin], hm(start), hm(end))
    return net, {net.station_codes[s]: v for s, v in found.items()}


def arrival(found, dest="D", max_trains=2):
    journeys = found.get(dest, [[], [], []])[max_trains - 1]
    return min((j.arr for j in journeys), default=None)


def via(net, journey):
    return [net.station_codes[net.stop_station[leg.alight_stop]] for leg in journey.legs[:-1]]


def test_any_profile_takes_the_fast_change():
    net, found = search(FAST | SLOW, "any")
    assert arrival(found) == hm("10:30")
    assert via(net, found["D"][1][0]) == ["X"]


def test_stroller_avoids_a_transfer_station_without_step_free_route():
    net, found = search(FAST | SLOW, "stroller")
    assert arrival(found) == hm("10:50")
    assert via(net, found["D"][1][0]) == ["Y"]


def test_stroller_has_no_route_if_the_only_change_needs_stairs():
    _, found = search(FAST, "stroller")
    assert "D" not in found


def test_change_on_one_island_platform_is_step_free_even_at_a_station_without_lifts():
    access = ACCESS | {"X": station("X", {"1": "no", "2": "no"}, islands={"1-2": ["1", "2"]})}
    _, found = search(FAST, "stroller", access=access)
    assert arrival(found) == hm("10:30")  # 2 min same platform + 3 min buffer = exactly 10:15


def test_unknown_counts_as_not_step_free():
    access = ACCESS | {"Y": station("Y", {"1": "yes", "2": "unknown"})}
    _, found = search(FAST | SLOW, "stroller", access=access)
    assert "D" not in found


def test_stroller_cannot_start_or_end_at_a_platform_that_is_not_step_free():
    access = ACCESS | {"O": station("O", {"1": "no", "2": "no"})}
    _, found = search(FAST | SLOW, "stroller", access=access)
    assert found == {}
    access = ACCESS | {"D": station("D", {"1": "unknown"})}
    _, found = search(FAST | SLOW, "stroller", access=access)
    assert "D" not in found


def test_unmatched_platform_counts_as_step_free_only_when_it_must_be_a_known_track():
    direct = {"T9": [("O", "1", "10:00", "10:00"), ("D", "?", "10:20", "10:20")]}  # timetable gives no platform
    _, found = search(direct, "stroller")
    assert arrival(found, max_trains=1) == hm("10:20")  # D's only track is step-free

    # the timetable uses more platforms at D than EPIAP knows: platform 7 could be new, so unknown
    three = {
        "T9": [("O", "1", "10:00", "10:00"), ("D", "7", "10:20", "10:20")],
        "T10": [("O", "1", "11:00", "11:00"), ("D", "1", "11:20", "11:20")],
        "T11": [("O", "1", "11:30", "11:30"), ("D", "2", "11:50", "11:50")],
    }
    access = ACCESS | {"D": station("D", {"1": "yes", "2": "yes"})}
    _, found = search(three, "stroller", access=access)
    assert hm("10:20") not in [j.arr for j in found["D"][0]]


def test_stroller_needs_three_extra_minutes_to_change():
    tight = SLOW | {"T4": [("Y", "2", "10:24", "10:24"), ("D", "1", "10:44", "10:44")]}  # 4 min at Y
    _, found = search(tight, "any")
    assert arrival(found) == hm("10:44")
    _, found = search(tight, "stroller")
    assert "D" not in found  # needs 2 + 3 = 5 minutes


def test_ns_ruled_out_connection_is_not_used():
    _, found = search(FAST | SLOW, "any", transfers=[("T1", "T2", "X", "1", "2", "impossible")])
    assert arrival(found) == hm("10:50")


def test_ns_short_connection_beats_the_default_transfer_time():
    minutes = MINUTES | {"X": 6}
    _, found = search(FAST, "any", minutes=minutes)
    assert "D" not in found  # 10:10 + 6 min > 10:15
    _, found = search(FAST, "any", minutes=minutes, transfers=[("T1", "T2", "X", "1", "2", "possible")])
    assert arrival(found) == hm("10:30")  # NS lists this 5-minute connection as possible


def test_through_train_under_a_new_number_is_not_a_change():
    trips = {
        "A": [("O", "1", "10:00", "10:00"), ("X", "1", "10:10", "10:10")],
        "B": [("X", "1", "10:12", "10:12"), ("D", "1", "10:30", "10:30")],
    }
    net, found = search(trips, "stroller", transfers=[("A", "B", "X", "1", "1", "possible")])
    j = found["D"][0][0]  # found with one train
    assert j.changes == 0 and j.arr == hm("10:30")


def test_sprinter_set_skips_intercity():
    trips = FAST | {"IC": [("O", "1", "10:05", "10:05"), ("D", "1", "10:20", "10:20")]}
    categories = {"IC": ("NS", "Intercity")}
    _, found = search(trips, "any", categories=categories)
    assert arrival(found, max_trains=1) == hm("10:20")
    _, found = search(trips, "any", categories=categories, train_set="sprinter")
    assert arrival(found, max_trains=1) is None
    assert arrival(found, max_trains=2) == hm("10:30")


def test_ns_marks_decide_before_the_category():
    trips = FAST | {"IC": [("O", "1", "10:05", "10:05"), ("D", "1", "10:20", "10:20")]}
    categories = {"IC": ("NS", "Intercity"), "T1": ("Arriva", "Stoptrein")}
    # an intercity NS marks accessible joins the trains without steps, and the journey says it takes one
    net, found = search(trips, "any", categories=categories, train_set="sprinter", step_free={"IC": True})
    assert arrival(found, max_trains=1) == hm("10:20")
    assert summarise(net, found["D"][0]).encode()[6:] == [1]
    assert summarise(net, found["D"][1]).intercity  # also the typical journey when a change is allowed
    # a regional train NS marks not accessible drops out (via Y at 10:50, not via X at 10:30); the unmarked intercity stays out
    _, found = search(trips | SLOW, "any", categories=categories, train_set="sprinter", step_free={"T1": False})
    assert arrival(found, max_trains=1) is None and arrival(found, max_trains=2) == hm("10:50")
    # with all trains, the marks don't matter
    _, found = search(trips, "any", categories=categories, step_free={"T1": False, "IC": False})
    assert arrival(found, max_trains=1) == hm("10:20")


def test_first_train_must_leave_within_the_window():
    _, found = search(FAST, "any", start="09:00", end="09:59")
    assert found == {}


def test_the_summary_records_the_tracks_used():
    net, found = search(FAST | SLOW, "stroller")
    s = summarise(net, found["D"][1])
    assert s.via == ("Y",) and s.tracks == ("2", "1", "2", "1")  # leave O from 2, change at Y from 1 to 2, arrive on 1
    assert s.encode()[4:] == ["Y", "2|1|2|1"]


def test_profile_keeps_only_sensible_journeys_and_summarises_them():
    trips = {}
    for i, dep in enumerate(["10:00", "10:30", "11:00", "11:30"]):
        h, m = map(int, dep.split(":"))
        arr = f"{h:02d}:{m + 20:02d}"
        trips[f"S{i}"] = [("O", "1", dep, dep), ("D", "1", arr, arr)]
    # a slow train leaving 10:05 and arriving after the 10:30 one: never a sensible choice
    trips["SLOWPOKE"] = [("O", "2", "10:05", "10:05"), ("D", "1", "10:55", "10:55")]
    net, found = search(trips, "any", start="10:00", end="11:30")
    journeys = found["D"][0]
    assert sorted(j.dep for j in journeys) == [hm(t) for t in ["10:00", "10:30", "11:00", "11:30"]]
    s = summarise(net, journeys)
    assert (s.median, s.fastest, s.changes) == (20, 20, 0)
