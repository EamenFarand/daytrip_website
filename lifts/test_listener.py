"""The lift listener's rules, on hand-made SIRI-FM messages shaped like the real feed."""

import gzip
from datetime import datetime, timedelta, timezone

from listener import FULL_STATE_MIN, Publisher, State, parse, problem

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)


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
