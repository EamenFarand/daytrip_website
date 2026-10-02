"""The nightly job only builds when something changed since the live build."""

from datetime import date

from stepfree.inputs import needs_build

NOW = {"gtfs": "a", "epiap": "b", "iff": "c", "overrides": "d", "code": "e"}
LIVE = {"inputs": dict(NOW), "days": {"weekday": "2026-10-28", "saturday": "2026-10-24"}}


def test_builds_when_there_is_no_live_build():
    assert needs_build(None, NOW, date(2026, 10, 3))[0]
    assert needs_build({"days": {}}, NOW, date(2026, 10, 3))[0]  # an older build without inputs


def test_skips_when_nothing_changed():
    assert needs_build(LIVE, NOW, date(2026, 10, 3)) == (False, "nothing changed since the live build")


def test_builds_when_a_source_or_the_code_changed():
    build, reason = needs_build(LIVE, NOW | {"gtfs": "new", "code": "new"}, date(2026, 10, 3))
    assert build and reason == "changed: gtfs, code"


def test_builds_when_a_timetable_day_has_passed():
    assert needs_build(LIVE, NOW, date(2026, 10, 24)) == (False, "nothing changed since the live build")  # that day is still fine
    assert needs_build(LIVE, NOW, date(2026, 10, 25))[0]
