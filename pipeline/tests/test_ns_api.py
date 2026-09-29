"""Our journeys vs the NS journey planner. Skipped until NS_API_KEY is in .env."""

import pytest

from stepfree.config import env

pytestmark = pytest.mark.skipif(not env("NS_API_KEY"), reason="NS_API_KEY not set (docs/NEEDS_DAAN.md)")


def test_matches_ns_journey_planner_for_most_pairs():
    from stepfree.ns_check import PAIRS, compare

    problems = compare()
    # a few differences are expected (NS may use tighter or looser changes than we do), not many
    assert len(problems) <= len(PAIRS) // 5, "\n".join(problems)
