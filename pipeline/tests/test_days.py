"""Choosing the reference days: the most normal Tue/Wed/Thu and Saturday (gtfs.choose_days)."""

from datetime import date, timedelta

import polars as pl

from stepfree.gtfs import choose_days, timetable_change

TODAY = date(2026, 10, 7)  # a Wednesday
LINE = [["A", "B", "W", "C"], ["C", "W", "B", "A"]]  # two through trains


def span(first: date, last: date) -> list[date]:
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


ALL = span(date(2026, 10, 8), date(2026, 12, 2))  # the eight weeks the build looks ahead


def feed(services: dict[str, tuple[list[date], list[list[str]]]]) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """calls, trips and dates for {service_id: (its dates, the stations of each of its trips)}."""
    calls, trips, dates = [], [], []
    for sid, (days, trip_stations) in services.items():
        dates += [{"service_id": sid, "date": d} for d in days]
        for i, stations in enumerate(trip_stations):
            trips.append({"trip_id": f"{sid}{i}", "service_id": sid})
            calls += [{"trip_id": f"{sid}{i}", "station": s} for s in stations]
    return pl.DataFrame(calls), pl.DataFrame(trips), pl.DataFrame(dates)


def test_a_day_with_a_station_closed_loses_even_with_more_trips():
    works = set(span(date(2026, 10, 20), date(2026, 10, 31)))  # like Wolfheze in Oct 2026
    split = [["A", "B"], ["C"], ["B", "A"], ["C"], ["A", "B"]]  # the through trains cut in two: more trips
    calls, trips, dates = feed({"normal": ([d for d in ALL if d not in works], LINE), "works": (sorted(works), split)})
    assert choose_days(calls, trips, dates, TODAY) == {"weekday": date(2026, 10, 8), "saturday": date(2026, 10, 10)}


def test_event_only_stops_do_not_count():
    calls, trips, dates = feed({"normal": (ALL, LINE), "match": ([date(2026, 10, 14)], [["STADION"]])})
    assert choose_days(calls, trips, dates, TODAY)["weekday"] == date(2026, 10, 8)  # not the match day


def test_the_yearly_timetable_change_is_the_sunday_after_the_second_saturday_of_december():
    assert [timetable_change(date(y, 6, 1)) for y in (2023, 2024, 2025, 2026)] == [
        date(2023, 12, 10), date(2024, 12, 15), date(2025, 12, 14), date(2026, 12, 13)]
    assert timetable_change(date(2026, 12, 13)) == date(2027, 12, 12)  # on the day itself: the next one


def test_stays_in_the_running_timetable_while_it_has_a_day_left():
    old = span(date(2026, 11, 26), date(2026, 12, 12))
    new = span(date(2026, 12, 13), date(2027, 1, 20))
    more = LINE + [["A", "B", "W", "C"]]  # next year's timetable has an extra train, so its days have more calls
    calls, trips, dates = feed({"old": (old, LINE), "new": (new, more)})
    assert choose_days(calls, trips, dates, date(2026, 11, 25)) == {"weekday": date(2026, 11, 26), "saturday": date(2026, 11, 28)}
    # Friday 11 Dec: no Tue/Wed/Thu left in this year's timetable, but its last Saturday is
    assert choose_days(calls, trips, dates, date(2026, 12, 11)) == {"weekday": date(2026, 12, 15), "saturday": date(2026, 12, 12)}


def test_looks_eight_weeks_ahead_for_a_saturday_without_works():
    works = {date(2026, 10, 10) + timedelta(weeks=i) for i in range(4)}  # every Saturday in the first four weeks
    calls, trips, dates = feed({"normal": ([d for d in ALL if d not in works], LINE), "works": (sorted(works), [["A", "B"], ["C"]])})
    assert choose_days(calls, trips, dates, TODAY)["saturday"] == date(2026, 11, 7)
