"""Cost-optimal refuelling plan. Pure Python, no Django, fully unit-tested.

Problem: drive ``total_miles`` along a line. Candidate stops sit at known mile
markers with a price per gallon. The tank holds ``range_miles`` of fuel and you
may buy any amount at a stop. Minimise money spent.

This is the classic "gas station" problem, solved exactly by a greedy rule:

* Standing at a stop, if a CHEAPER stop is reachable on the current range,
  buy only enough to reach the first such stop (never pay more than needed).
* Otherwise nothing ahead is cheaper, so fill the tank here, then drive to the
  cheapest stop in range (the destination counts as free, i.e. cheapest).

The route end is modelled as a zero-price stop so "buy just enough to arrive"
falls out of the first rule.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .errors import NoFeasiblePlan

EPS = 1e-9
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Candidate:
    """A place fuel can be bought. ``mile`` is the distance along the route."""

    mile: float
    price: float
    ref: object = None  # opaque payload (e.g. the FuelStation row)


@dataclass(frozen=True)
class Purchase:
    candidate: Candidate
    gallons: float
    cost: Decimal


@dataclass(frozen=True)
class FuelPlan:
    purchases: list[Purchase]
    total_gallons: float
    total_cost: Decimal


def _money(price: float, gallons: float) -> Decimal:
    return (Decimal(repr(price)) * Decimal(repr(gallons))).quantize(CENT, ROUND_HALF_UP)


def _consolidate(stops: list[Candidate], bought: dict[int, float], rng: float, min_miles: float) -> None:
    """Merge purchases smaller than ``min_miles`` of range into the preceding purchase (in place).

    The first purchase (the trip start) is never merged. A merge is only done when the
    tank has room: after buying at the earlier stop the level may not exceed ``rng``.
    """
    while True:
        order = sorted(bought)
        levels, fuel, last = {}, 0.0, 0
        for idx in order:  # tank level right after each purchase
            fuel = fuel - (stops[idx].mile - stops[last].mile) + bought[idx]
            levels[idx], last = fuel, idx
        small = [p for p in range(1, len(order)) if bought[order[p]] < min_miles]
        for pos in sorted(small, key=lambda p: bought[order[p]]):
            prev, cur = order[pos - 1], order[pos]
            if levels[prev] + bought[cur] <= rng + EPS:
                bought[prev] += bought.pop(cur)
                break
        else:
            return


def plan_fuel(
    candidates: list[Candidate],
    total_miles: float,
    range_miles: float,
    mpg: float,
    min_saving: float = 0.0,
    min_purchase_gallons: float = 0.0,
) -> FuelPlan:
    """Return the cheapest sequence of purchases for a trip that starts EMPTY.

    ``candidates`` must include one at mile 0 (the origin fill-up) so the trip can start.

    ``min_saving`` ($/gal) makes a stop only count as "cheaper" if it saves at least that
    much. 0 gives the exact optimum; a small positive value avoids stopping to buy a few
    gallons for a fraction of a cent (cost impact is bounded by min_saving x gallons).

    ``min_purchase_gallons`` folds any real stop that would sell fewer gallons than this into
    the previous purchase when the tank can hold it, so a trip never stops for a few gallons.
    """
    stops = sorted(candidates, key=lambda c: (c.mile, c.price))
    if not stops or stops[0].mile > EPS:
        raise NoFeasiblePlan("There is no fuel available at the start of the route.")
    if total_miles <= EPS:
        return FuelPlan([], 0.0, Decimal("0.00"))

    dest = Candidate(total_miles, 0.0, None)
    stops = [s for s in stops if s.mile < total_miles - EPS] + [dest]

    bought: dict[int, float] = {}  # index in `stops` -> miles of fuel bought there
    i, fuel = 0, 0.0
    while i < len(stops) - 1:
        cur = stops[i]
        ahead = []
        for j in range(i + 1, len(stops)):
            if stops[j].mile - cur.mile > range_miles + EPS:
                break
            ahead.append(j)
        if not ahead:
            raise NoFeasiblePlan(
                f"No fuel stop within {range_miles:.0f} miles after mile {cur.mile:.0f}: "
                "the route cannot be completed on one tank."
            )
        cheaper = next((j for j in ahead if stops[j].price < cur.price - min_saving - EPS), None)
        if cheaper is not None:
            target = cheaper
            buy = max(0.0, (stops[cheaper].mile - cur.mile) - fuel)
        else:
            # Nothing cheaper in range (the free destination would have matched): fill up,
            # then go to the cheapest stop in range (the farthest of any within min_saving of it).
            floor = min(stops[j].price for j in ahead)
            target = max(j for j in ahead if stops[j].price <= floor + min_saving + EPS)
            buy = range_miles - fuel
        if buy > EPS:
            bought[i] = bought.get(i, 0.0) + buy
            fuel += buy
        fuel -= stops[target].mile - cur.mile
        i = target

    if min_purchase_gallons > 0:
        _consolidate(stops, bought, range_miles, min_purchase_gallons * mpg)

    purchases, total_gal, total_cost = [], 0.0, Decimal("0.00")
    for idx in sorted(bought):
        gallons = bought[idx] / mpg
        cost = _money(stops[idx].price, gallons)
        purchases.append(Purchase(stops[idx], gallons, cost))
        total_gal += gallons
        total_cost += cost
    return FuelPlan(purchases, total_gal, total_cost)
