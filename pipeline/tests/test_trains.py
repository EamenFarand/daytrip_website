"""Trains without steps, from NS's own marks per train unit (stepfree.trains)."""

import json
from datetime import date, datetime, timezone

from stepfree import trains

WED, SAT = date(2026, 11, 4), date(2026, 11, 21)


def record(days: dict[str, tuple[str, str]], updated: str = "2026-10-08T03:00:00Z") -> dict:
    """The listener's record: per date, (train numbers with accessible units only, those with one that isn't)."""
    return {"v": 1, "updated": updated, "days": {d: {"yes": yes, "no": no} for d, (yes, no) in days.items()}}


def test_an_intercity_counts_after_three_accessible_days_and_never_after_one_with_steps():
    r = record({
        "2026-10-05": ("1100 700 4000", "702"),  # Mon
        "2026-10-06": ("1100 700", "702 31073"),
        "2026-10-07": ("1100", "700"),  # 700 ran once with a unit that isn't accessible
        "2026-10-03": ("1100", ""),  # a Saturday: doesn't count for weekdays
    })
    # 4000 seen once: no verdict, so its category decides
    assert trains.verdicts(r, WED) == {"1100": True, "700": False, "702": False, "31073": False}


def test_saturdays_and_weekdays_count_apart():
    r = record({"2026-09-19": ("1100", ""), "2026-09-26": ("1100", ""), "2026-10-03": ("1100", "")})
    assert trains.verdicts(r, SAT) == {"1100": True}
    assert trains.verdicts(r, WED) == {}


def test_only_the_last_four_weeks_of_the_same_yearly_timetable_count():
    r = record({
        "2026-09-07": ("1100", ""), "2026-09-08": ("1100", ""), "2026-09-09": ("1100", ""),  # more than four weeks old
        "2026-12-15": ("1200", ""), "2026-12-16": ("1200", ""), "2026-12-17": ("1200", ""),  # next year's timetable
    })
    assert trains.verdicts(r, WED) == {}
    assert trains.verdicts(r, date(2026, 12, 16)) == {"1200": True}
    assert trains.verdicts(None, WED) == {}


def test_loads_a_local_file_and_ignores_an_old_record(tmp_path, monkeypatch):
    f = tmp_path / "trains.json"
    f.write_text(json.dumps(record({"2026-10-07": ("1100", "")})))
    monkeypatch.setenv("STEPFREE_TRAINS", str(f))
    assert trains.load(datetime(2026, 10, 9, tzinfo=timezone.utc))["days"]
    assert trains.load(datetime(2026, 10, 30, tzinfo=timezone.utc)) is None  # more than two weeks old


def test_says_nothing_on_stdout(tmp_path, monkeypatch, capsys):
    """stepfree.inputs' stdout goes to GitHub Actions as key=value lines; a message there stopped the deploy of 7 Oct."""
    f = tmp_path / "trains.json"
    f.write_text(json.dumps(record({}, updated="2026-01-01T00:00:00Z")))
    monkeypatch.setenv("STEPFREE_TRAINS", str(f))
    assert trains.load() is None
    assert capsys.readouterr().out == ""


def test_the_digest_changes_with_a_verdict_not_with_every_new_day():
    r = record({"2026-10-05": ("1100", ""), "2026-10-06": ("1100", ""), "2026-10-07": ("1100", "")})
    today = date(2026, 10, 8)
    before = trains.digest(r, today)
    r["days"]["2026-10-08"] = {"yes": "1100", "no": ""}  # one more day, same verdict
    assert trains.digest(r, today) == before
    r["days"]["2026-10-08"] = {"yes": "", "no": "1100"}
    assert trains.digest(r, today) != before
    assert trains.digest(None, today) == "none"
