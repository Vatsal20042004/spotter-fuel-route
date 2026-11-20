import random

import pytest

from fuel.services.errors import NoFeasiblePlan
from fuel.services.optimizer import Candidate, plan_fuel

RANGE, MPG = 500, 10


def C(mile, price):
    return Candidate(float(mile), float(price))


def brute_force_cost(cands, total, rng):
    """Reference DP over integer miles of fuel: exact optimum for integer distances."""
    stops = sorted(cands, key=lambda c: c.mile) + [Candidate(total, 0.0)]
    INF = float("inf")
    best = {0: 0.0}  # fuel on arrival (miles) -> min cost, at stop index i
    for i, cur in enumerate(stops[:-1]):
        gap = int(stops[i + 1].mile - cur.mile)
        nxt = {}
        for fuel, cost in best.items():
            for target in range(fuel, rng + 1):  # fuel level after buying
                c = cost + (target - fuel) * cur.price / MPG
                left = target - gap
                if left >= 0 and c < nxt.get(left, INF):
                    nxt[left] = c
        best = nxt
        if not best:
            return None
    return min(best.values())


def test_short_trip_buys_only_what_it_burns():
    plan = plan_fuel([C(0, 3.0)], 100, RANGE, MPG)
    assert plan.total_gallons == pytest.approx(10)
    assert str(plan.total_cost) == "30.00"
    assert len(plan.purchases) == 1


def test_buys_just_enough_to_reach_cheaper_stop_then_fills_there():
    plan = plan_fuel([C(0, 4.0), C(200, 3.0)], 700, RANGE, MPG)
    by_mile = {p.candidate.mile: p.gallons for p in plan.purchases}
    assert by_mile[0] == pytest.approx(20)  # exactly enough to reach the cheap stop
    assert by_mile[200] == pytest.approx(50)  # 500 miles' worth, covering the rest
    assert str(plan.total_cost) == "230.00"


def test_expensive_stop_is_skipped_when_tank_can_cover():
    plan = plan_fuel([C(0, 3.0), C(100, 5.0), C(300, 5.0)], 400, RANGE, MPG)
    assert [p.candidate.mile for p in plan.purchases] == [0]


def test_gap_longer_than_range_is_infeasible():
    with pytest.raises(NoFeasiblePlan):
        plan_fuel([C(0, 3.0), C(600, 3.0)], 900, RANGE, MPG)


def test_exactly_one_tank_needs_no_second_stop():
    plan = plan_fuel([C(0, 3.0)], 500, RANGE, MPG)
    assert len(plan.purchases) == 1 and plan.total_gallons == pytest.approx(50)


def test_missing_origin_station_is_infeasible():
    with pytest.raises(NoFeasiblePlan):
        plan_fuel([C(50, 3.0)], 100, RANGE, MPG)


def test_total_gallons_equals_trip_distance_over_mpg():
    random.seed(7)
    cands = [C(0, 3.5)] + [C(m, random.uniform(2.8, 3.8)) for m in range(40, 2400, 55)]
    plan = plan_fuel(cands, 2400, RANGE, MPG)
    assert plan.total_gallons == pytest.approx(2400 / MPG)
    assert sum(p.cost for p in plan.purchases) == plan.total_cost


def test_never_exceeds_tank_between_purchases():
    random.seed(11)
    cands = [C(0, 3.5)] + [C(m, random.uniform(2.8, 3.8)) for m in range(30, 3000, 47)]
    plan = plan_fuel(cands, 3000, RANGE, MPG)
    miles = [p.candidate.mile for p in plan.purchases] + [3000]
    assert all(b - a <= RANGE + 1e-6 for a, b in zip(miles, miles[1:], strict=False))


@pytest.mark.parametrize("seed", range(25))
def test_matches_exact_dp_on_random_instances(seed):
    rnd = random.Random(seed)
    total = rnd.randint(300, 1500)
    miles = sorted(rnd.sample(range(1, total), rnd.randint(4, 14)))
    cands = [C(0, round(rnd.uniform(2.5, 4.0), 2))] + [C(m, round(rnd.uniform(2.5, 4.0), 2)) for m in miles]
    expected = brute_force_cost(cands, total, RANGE)
    if expected is None:
        with pytest.raises(NoFeasiblePlan):
            plan_fuel(cands, total, RANGE, MPG)
        return
    plan = plan_fuel(cands, total, RANGE, MPG)
    assert float(plan.total_cost) == pytest.approx(expected, abs=0.1 * len(plan.purchases) + 0.05)


def test_min_saving_reduces_stops_with_bounded_cost_impact():
    random.seed(3)
    cands = [C(0, 3.3)] + [C(m, 3.0 + random.uniform(0, 0.08)) for m in range(25, 1500, 30)]
    exact = plan_fuel(cands, 1500, RANGE, MPG)
    practical = plan_fuel(cands, 1500, RANGE, MPG, min_saving=0.05)
    assert len(practical.purchases) <= len(exact.purchases)
    assert practical.total_cost - exact.total_cost <= round(0.05 * 150, 2) + 1


def test_tiny_purchases_are_folded_into_previous_stop():
    # B is only 20 miles past A, so the greedy plan buys 2 gallons at A just to reach it.
    cands = [C(0, 3.50), C(200, 3.00), C(220, 2.90)]
    exact = plan_fuel(cands, 600, RANGE, MPG)
    merged = plan_fuel(cands, 600, RANGE, MPG, min_purchase_gallons=5)
    assert [p.candidate.mile for p in exact.purchases] == [0, 200, 220]
    assert [p.candidate.mile for p in merged.purchases] == [0, 220]
    assert merged.total_gallons == pytest.approx(60)
