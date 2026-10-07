"""The listener's rules, on hand-made SIRI-FM messages shaped like the real feed, and on real NS journey messages."""

import gzip
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from listener import FULL_STATE_MIN, Publisher, State, Trains, parse, parse_rit, problem

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)
TESTDATA = Path(__file__).parent / "testdata"  # real InfoPlus RIT messages of 7 Oct 2026 (NDOV Loket, CC0)


def condition(lift: str, status: str, start: str, end: str | None = None) -> str:
    validity = f"<StartTime>{start}</StartTime>" + (f"<EndTime>{end}</EndTime>" if end else "")
    return (f"<FacilityCondition><FacilityRef>NL:CHB:LiftEquipment:{lift}</FacilityRef>"
            f"<FacilityStatus><Status>{status}</Status></FacilityStatus><ValidityPeriod>{validity}</ValidityPeriod></FacilityCondition>")


def message(*conditions: str) -> bytes:
    xml = ('<ServiceDelivery xmlns="http://www.siri.org.uk/siri"><FacilityMonitoringDelivery>'
           f"<ResponseTimestamp>2026-10-02T02:02:00Z</ResponseTimestamp>{''.join(conditions)}"
           "</FacilityMonitoringDelivery></ServiceDelivery>")
    return gzip.compress(xml.encode())


def full_state(out: dict[str, str] | None = None) -> list[dict]:
    """A nightly full state: every lift available, except those in `out`."""
    out = out or {}
    xml = message(*(condition(f"84000{i:02d}_001", out.get(f"84000{i:02d}_001", "available"), "2026-01-01T00:00:00Z")
                    for i in range(FULL_STATE_MIN + 10)))
    return parse(xml)[0]


def test_reads_conditions_and_heartbeats():
    conditions, heartbeat = parse(message(condition("8400058_013", "notAvailable", "2024-06-19T14:30:29.00Z")))
    assert conditions == [{"id": "8400058_013", "status": "notAvailable", "start": "2024-06-19T14:30:29.00Z", "end": None}]
    assert not heartbeat
    beat = b'<HeartbeatNotification xmlns="http://www.siri.org.uk/siri"><Status>true</Status></HeartbeatNotification>'
    assert parse(beat) == ([], True)


def test_the_full_state_replaces_everything_and_changes_add_to_it():
    s = State()
    s.apply([{"id": "OLD_001", "status": "notAvailable", "start": "2026-01-01T00:00:00Z", "end": None}], NOW)
    s.apply(full_state({"8400001_001": "notAvailable"}), NOW)
    assert "OLD_001" not in s.lifts and s.full_state_at == NOW
    assert [o["id"] for o in s.payload(NOW)["out"]] == ["8400001_001"]
    later = NOW + timedelta(hours=3)
    s.apply(parse(message(condition("8400001_001", "available", "2026-10-02T13:00:00Z")))[0], later)
    s.apply(parse(message(condition("8400002_001", "notAvailable", "2026-10-02T13:05:00Z")))[0], later)
    assert [o["id"] for o in s.payload(later)["out"]] == ["8400002_001"]
    assert s.full_state_at == NOW and s.last_message_at == later


def test_the_newest_valid_condition_wins():
    s = State()
    s.lifts["A"] = [  # Nijmegen Goffert on 2 Oct: out in the morning, working again since the evening
        {"id": "A", "status": "notAvailable", "start": "2026-09-22T06:56:50Z", "end": None},
        {"id": "A", "status": "available", "start": "2026-09-22T22:18:42Z", "end": None},
    ]
    s.lifts["B"] = [  # an outage that has ended: the older "unknown" applies again
        {"id": "B", "status": "unknown", "start": "2026-08-03T11:24:38Z", "end": None},
        {"id": "B", "status": "notAvailable", "start": "2026-09-05T22:00:00Z", "end": "2026-10-01T22:00:00Z"},
    ]
    s.lifts["C"] = [  # a planned outage that hasn't started yet
        {"id": "C", "status": "available", "start": "2026-01-01T00:00:00Z", "end": None},
        {"id": "C", "status": "notAvailable", "start": "2026-10-05T06:00:00Z", "end": "2026-10-09T18:00:00Z"},
    ]
    assert [s.current(k, NOW)["status"] for k in "ABC"] == ["available", "unknown", "available"]
    assert s.current("C", datetime(2026, 10, 6, tzinfo=timezone.utc))["status"] == "notAvailable"


def test_a_lift_that_comes_back_is_listed_as_back_for_half_an_hour():
    s = State()
    s.apply(full_state({"8400001_001": "notAvailable"}), NOW)
    assert [o["status"] for o in s.payload(NOW)["out"]] == ["notAvailable"]  # last seen out at 12:00
    s.apply(parse(message(condition("8400001_001", "available", "2026-10-02T12:05:00Z")))[0], NOW + timedelta(minutes=5))
    back = [{"id": "8400001_001", "status": "back", "since": "2026-10-02T12:00:00Z", "until": None}]
    assert s.payload(NOW + timedelta(minutes=5))["out"] == back
    assert s.payload(NOW + timedelta(minutes=29))["out"] == back
    assert s.payload(NOW + timedelta(minutes=30))["out"] == []
    s.apply(parse(message(condition("8400001_001", "notAvailable", "2026-10-02T12:40:00Z")))[0], NOW + timedelta(minutes=40))
    assert [o["status"] for o in s.payload(NOW + timedelta(minutes=40))["out"]] == ["notAvailable"]  # out again: a plain outage


def test_a_resend_does_not_pile_up():
    s = State()
    for _ in range(5):
        s.apply(parse(message(condition("8400477_001", "available", "2026-09-22T22:18:42.00Z")))[0], NOW)
    assert len(s.lifts["8400477_001"]) == 1


def test_never_publishes_an_implausible_state():
    s = State()
    s.apply(parse(message(condition("8400001_001", "notAvailable", "2026-10-02T10:00:00Z")))[0], NOW)
    assert "no full state" in problem(s.payload(NOW))
    s.apply(full_state(), NOW)
    assert problem(s.payload(NOW)) is None
    s.apply(full_state({f"84000{i:02d}_001": "notAvailable" for i in range(200)}), NOW)
    assert "out" in problem(s.payload(NOW))
    assert problem({"full_state_at": "2026-10-02T02:02:00Z", "lifts": 400, "out": [{"status": "back"}] * 250}) is None  # working again


def test_publishes_on_change_but_not_too_often(tmp_path):
    s = State()
    s.apply(full_state(), NOW)
    p = Publisher(None, None, None, dry_run_file=tmp_path / "lifts.json")
    assert p.due(s.payload(NOW), NOW)
    p.publish(s.payload(NOW), NOW)
    assert (tmp_path / "lifts.json").exists()
    assert not p.due(s.payload(NOW + timedelta(minutes=5)), NOW + timedelta(minutes=5))  # nothing changed
    s.apply(parse(message(condition("8400001_001", "notAvailable", "2026-10-02T12:01:00Z")))[0], NOW)
    assert not p.due(s.payload(NOW + timedelta(minutes=1)), NOW + timedelta(minutes=1))  # changed, but too soon
    assert p.due(s.payload(NOW + timedelta(minutes=2)), NOW + timedelta(minutes=2))
    p.publish(s.payload(NOW + timedelta(minutes=2)), NOW + timedelta(minutes=2))
    assert p.due(s.payload(NOW + timedelta(minutes=12)), NOW + timedelta(minutes=12))  # every 10 minutes regardless


def rit(day: str, *parts: tuple[str, list[str | None]]) -> bytes:
    """A journey message shaped like NS's: per part of the run, its train number and its units' accessible marks."""
    def stop(i: int, mark: str | None) -> str:
        unit = "<MaterieelDeelSoort>ICNG</MaterieelDeelSoort>" + (f"<MaterieelDeelToegankelijk>{mark}</MaterieelDeelToegankelijk>" if mark else "")
        return f"<LogischeRitDeelStation><Station><StationCode>S{i}</StationCode></Station><MaterieelDeel>{unit}</MaterieelDeel></LogischeRitDeelStation>"
    body = "".join(f"<LogischeRitDeel><LogischeRitDeelNummer>{n}</LogischeRitDeelNummer>{''.join(stop(i, m) for i, m in enumerate(marks))}</LogischeRitDeel>"
                   for n, marks in parts)
    xml = ('<ns2:PutReisInformatieBoodschapIn xmlns="urn:ns:cdm:reisinformatie:data:rit:5" xmlns:ns2="urn:ns:cdm:reisinformatie:message:ritinfo:5">'
           f"<ReisInformatieProductRitInfo><RitInfo><TreinNummer>{parts[0][0]}</TreinNummer><TreinDatum>{day}</TreinDatum>"
           f"<LogischeRit>{body}</LogischeRit></RitInfo></ReisInformatieProductRitInfo></ns2:PutReisInformatieBoodschapIn>")
    return gzip.compress(xml.encode())


def test_reads_ns_accessible_mark_per_part_of_a_train():
    assert parse_rit(rit("2026-10-07", ("1100", ["J", "J"]))) == [("2026-10-07", "1100", "J")]
    # one unit marked not accessible anywhere on the run is enough; a run continuing under another number has two parts
    assert parse_rit(rit("2026-10-07", ("1778", ["J", "N"]), ("2878", ["J"]))) == [("2026-10-07", "1778", "N"), ("2026-10-07", "2878", "J")]
    assert parse_rit(rit("2026-10-07", ("700", []))) == []  # no units listed: nothing
    assert parse_rit(rit("2026-10-07", ("701", ["J", None]))) == []  # a unit without the mark: nothing


def test_reads_real_journey_messages():
    read = lambda name: parse_rit((TESTDATA / name).read_bytes())
    assert read("rit-icd-1885-icng5.xml.gz") == [("2026-10-07", "1885", "J")]  # a five-car ICNG
    assert read("rit-icd-1887-icng8b.xml.gz") == [("2026-10-07", "1887", "N")]  # the ICNG built for Brussels: NS says not accessible
    assert read("rit-ic-1778-2878-ddz.xml.gz") == [("2026-10-07", "1778", "N"), ("2026-10-07", "2878", "N")]  # double-deckers, two parts


def test_a_train_seen_with_steps_once_stays_so_that_day(tmp_path):
    t = Trains()
    t.add([("2026-10-07", "700", "J"), ("2026-10-07", "700", "N"), ("2026-10-07", "700", "J"), ("2026-10-08", "700", "J")])
    assert t.days == {"2026-10-07": {"700": "N"}, "2026-10-08": {"700": "J"}}
    t.add([("2026-10-08", "11000", "J"), ("2026-10-08", "1100", "J"), ("2026-10-08", "702", "N")])
    assert t.payload(NOW)["days"]["2026-10-08"] == {"yes": "700 1100 11000", "no": "702"}  # numeric order
    t.prune(date(2026, 11, 12))  # 35 days kept
    assert list(t.days) == ["2026-10-08"]
    t.save(tmp_path / "trains.json")
    assert Trains.load(tmp_path / "trains.json").days == t.days
    assert Trains.load(tmp_path / "none.json").days == {}


def test_trains_get_their_own_key_and_are_published_whole(tmp_path):
    assert Publisher("a", "n", "t").url.endswith("/values/lifts")
    p = Publisher("a", "n", "t", dry_run_file=tmp_path / "trains-out.json", key="trains")
    assert p.url.endswith("/values/trains")
    t = Trains({"2026-10-07": {"1885": "J"}})
    p.publish(t.payload(NOW), NOW)
    assert '"1885"' in (tmp_path / "trains-out.json").read_text() and p.last_try == NOW


def test_the_state_survives_a_restart(tmp_path):
    s = State()
    s.apply(full_state({"8400001_001": "notAvailable", "8400002_001": "notAvailable"}), NOW)
    s.payload(NOW)
    s.apply(parse(message(condition("8400002_001", "available", "2026-10-02T12:05:00Z")))[0], NOW + timedelta(minutes=5))
    s.save(tmp_path / "state.json")
    again = State.load(tmp_path / "state.json")
    later = NOW + timedelta(minutes=10)
    assert again.full_state_at == NOW
    assert [(o["id"], o["status"]) for o in again.payload(later)["out"]] == [("8400001_001", "notAvailable"), ("8400002_001", "back")]
