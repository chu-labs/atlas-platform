from dataclasses import replace
from datetime import date

from atlas.domain.risk import WEIGHTS, band, risk_profile
from tests.conftest import make_claim

AS_OF = date(2026, 9, 13)


def test_weights_sum_to_100():
    assert sum(WEIGHTS.values()) == 100


def test_clean_building_scores_low(building):
    p = risk_profile(building, [], AS_OF)
    assert p.score < 30
    assert p.band in {"A", "B"}
    assert set(p.pillars) == set(WEIGHTS)


def test_claims_raise_the_score(building):
    claims = [make_claim(i, date(2026, 1, 1 + i % 20)) for i in range(25)]
    assert risk_profile(building, claims, AS_OF).score > risk_profile(building, [], AS_OF).score


def test_building_with_zero_lots_does_not_crash(building):
    b = replace(building, lots=0)
    claims = [make_claim(1, date(2026, 3, 1))]
    p = risk_profile(b, claims, AS_OF)
    assert 0 <= p.score <= 100


def test_declined_claims_are_ignored(building):
    declined = [make_claim(i, date(2026, 2, 1), status="declined") for i in range(10)]
    assert (
        risk_profile(building, declined, AS_OF).pillars["claims"]
        == risk_profile(building, [], AS_OF).pillars["claims"]
    )


def test_hazards_show_up_as_drivers(building):
    b = replace(building, flood_zone="high", bushfire_bal="29", cladding_flag=True)
    p = risk_profile(b, [], AS_OF)
    assert any("flood" in d for d in p.drivers)
    assert any("bushfire" in d for d in p.drivers)
    assert any("cladding" in d for d in p.drivers)


def test_bands():
    assert [band(s) for s in (0, 19, 20, 39, 40, 59, 60, 79, 80, 100)] == list("AABBCCDDEE")
