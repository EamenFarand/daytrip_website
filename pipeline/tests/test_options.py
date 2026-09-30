"""More options (a change, intercities, no pram) must never make a destination look worse.

Entries are [median, fastest, departures per hour, changes, "VIA|VIA"?] per change limit 0, 1, 2.
"""

import json

import pytest

from stepfree.precompute import more_options_never_worse
from stepfree.validate import ValidationError, check_router, validate


def test_allowing_a_change_keeps_the_direct_trains():
    # Utrecht C -> Abcoude, weekday: 3 direct trains of 20 min. With a change allowed there are more
    # journeys via Breukelen and the median became 31 min, so Abcoude fell out of "30 min".
    day = {"stroller": {"sprinter": {"AC": [[20, 20, 0.9, 0], [31, 20, 3.1, 1, "BKL"]]}}}
    more_options_never_worse(day)
    assert day["stroller"]["sprinter"]["AC"] == [[20, 20, 0.9, 0]]


def test_intercities_and_no_pram_never_look_worse():
    pram = [[45, 45, 2.9, 1, "DVD"]]
    day = {
        "stroller": {"sprinter": {"D": pram}, "all": {"D": pram}},
        "any": {"sprinter": {"D": [[49, 45, 4.3, 1, "ASDM"]]}, "all": {"D": [[49, 40, 4.3, 1, "ASDM"]]}},
    }
    more_options_never_worse(day)
    assert day["any"]["sprinter"]["D"] == pram  # the pram journeys work for anyone
    assert day["any"]["all"]["D"] == pram


def test_a_better_option_is_kept():
    levels = [[40, 40, 1.0, 0], [30, 25, 4.0, 1, "X"]]
    day = {"any": {"all": {"D": [list(e) for e in levels]}}}
    more_options_never_worse(day)
    assert day["any"]["all"]["D"] == levels


def test_on_the_same_typical_time_fewer_changes_win():
    day = {"any": {"all": {"D": [[30, 30, 2.0, 0], [30, 25, 4.0, 1, "X"]]}}}
    more_options_never_worse(day)
    assert day["any"]["all"]["D"] == [[30, 30, 2.0, 0]]


def test_pram_results_never_borrow_from_no_pram():
    day = {"stroller": {"all": {}}, "any": {"all": {"D": [[20, 20, 2.0, 0]]}}}
    more_options_never_worse(day)
    assert "D" not in day["stroller"]["all"]  # D may not be step-free: never invent a pram journey


def test_router_check_catches_a_slower_result_with_more_options():
    raw = {"O": {"weekday": {"stroller": {"all": {"D": [[30, 20, 2.0, 0]]}}, "any": {"all": {"D": [[30, 25, 2.0, 0]]}}}}}
    with pytest.raises(ValidationError, match="slower"):
        check_router(raw)


def test_validation_rejects_a_longer_typical_time_with_more_changes(tmp_path):
    (tmp_path / "origins").mkdir()
    (tmp_path / "meta.json").write_text("{}")
    (tmp_path / "stations.json").write_text(json.dumps([{"code": c, "status": "yes"} for c in ("O", "D", "X")]))
    doc = {"origin": "O", "results": {"weekday": {"any": {"all": {"D": [[20, 20, 1.0, 0], [31, 20, 3.0, 1, "X"]]}}}}}
    (tmp_path / "origins" / "O.json").write_text(json.dumps(doc))
    with pytest.raises(ValidationError, match="longer typical time"):
        validate(tmp_path, partial=True)
