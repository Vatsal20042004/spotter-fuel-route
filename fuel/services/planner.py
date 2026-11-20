"""Orchestrates one request: resolve -> route -> match stations -> optimise."""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal

import numpy as np
from django.conf import settings

from fuel.models import FuelStation

from .errors import NoFeasiblePlan
from .optimizer import Candidate, FuelPlan, plan_fuel, price_blind_cost
from .routing import CallTracker, Location, Route, fetch_route, resolve_location
from .spatial import build_profile, haversine_miles, stations_along_route

ORIGIN_REFERENCE_MILES = 100  # stations within this distance of the start price the origin fill-up


class StationIndex:
    """All stations held in memory as numpy arrays (6k rows -> well under 1 MB)."""

    _instance: StationIndex | None = None

    def __init__(self) -> None:
        rows = list(FuelStation.objects.all())
        self.rows = rows
        self.lat = np.array([r.lat for r in rows], dtype=float)
        self.lng = np.array([r.lng for r in rows], dtype=float)
        self.price = np.array([float(r.price) for r in rows], dtype=float)

    @classmethod
    def get(cls) -> StationIndex:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None


@dataclass(frozen=True)
class StationHit:
    """A station found along the route, with how far off the route it sits."""

    station: FuelStation
    detour_miles: float


@dataclass
class TripResult:
    start: Location
    end: Location
    route: Route
    plan: FuelPlan
    origin_price: float
    baselines: dict[str, Decimal | None]
    candidates_considered: int
    tracker: CallTracker
    range_miles: float
    mpg: float
    timings_ms: dict[str, float]


def plan_trip(
    start_text: str,
    end_text: str,
    range_miles: float | None = None,
    mpg: float | None = None,
) -> TripResult:
    range_miles = range_miles or settings.VEHICLE_RANGE_MILES
    mpg = mpg or settings.VEHICLE_MPG
    tracker = CallTracker()
    timings: dict[str, float] = {}
    t0 = time.perf_counter()

    start = resolve_location(start_text, tracker)
    end = resolve_location(end_text, tracker)
    route = fetch_route(start, end, tracker)
    timings["external_ms"] = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    index = StationIndex.get()
    if not index.rows:
        raise NoFeasiblePlan("Fuel station data is not loaded. Run `manage.py load_fuel_stations`.")

    profile = build_profile(route.coords, route.distance_miles)
    idx, miles, offsets = stations_along_route(
        profile, index.lat, index.lng, settings.MAX_STATION_DETOUR_MILES
    )
    candidates = [
        Candidate(float(m), float(index.price[i]), StationHit(index.rows[i], float(off)))
        for i, m, off in zip(idx, miles, offsets, strict=True)
    ]

    # The CSV has no station "at" the origin, so the first tank is priced at the average
    # of stations near the start (or the cheapest corridor station if none are that close).
    near_start = [c.price for c in candidates if c.mile <= ORIGIN_REFERENCE_MILES]
    if near_start:
        origin_price = float(np.mean(near_start))
    elif candidates:
        origin_price = min(c.price for c in candidates)
    else:
        # Nothing along the route: price the start from the stations nearest to it. A trip that
        # fits in one tank still works; a longer one will be reported as infeasible below.
        dist = haversine_miles(start.lat, start.lng, index.lat, index.lng)
        origin_price = float(np.mean(index.price[np.argsort(dist)[:25]]))
    origin = Candidate(0.0, origin_price, None)

    all_candidates = [origin, *candidates]
    plan = plan_fuel(
        all_candidates, route.distance_miles, range_miles, mpg,
        min_saving=settings.MIN_PRICE_ADVANTAGE,
        min_purchase_gallons=settings.MIN_PURCHASE_GALLONS,
    )
    gallons_needed = route.distance_miles / mpg
    avg_price = float(np.mean([c.price for c in all_candidates]))
    baselines = {
        "price_blind": price_blind_cost(all_candidates, route.distance_miles, range_miles, mpg),
        "corridor_average": (Decimal(repr(avg_price)) * Decimal(repr(gallons_needed))).quantize(
            Decimal("0.01")
        ),
    }
    timings["compute_ms"] = (time.perf_counter() - t1) * 1000
    timings["total_ms"] = (time.perf_counter() - t0) * 1000
    return TripResult(
        start, end, route, plan, round(origin_price, 4), baselines, len(candidates), tracker,
        range_miles, mpg,
        {k: round(v, 1) for k, v in timings.items()},
    )


def price_str(value: float | Decimal) -> str:
    return f"{Decimal(str(value)):.4f}"
