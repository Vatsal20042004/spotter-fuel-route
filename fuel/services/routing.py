"""Map/routing clients: OSRM (routing) and Nominatim (address -> coordinates).

Budget: the route itself costs exactly ONE OSRM call. If the caller passes
"lat,lng" coordinates no geocoding happens at all; free-text addresses cost one
Nominatim call each (so at most 3 external calls in the worst case). Every
result is cached, so repeating a request costs zero calls.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.core.cache import cache

from .errors import InvalidLocation, NoRouteFound, OutsideUSA, UpstreamError

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1609.344
# Rough bounding boxes (lat_min, lat_max, lng_min, lng_max): contiguous US, Alaska, Hawaii.
US_BOXES = [(24.3, 49.6, -125.1, -66.8), (51.0, 71.6, -170.0, -129.9), (18.8, 22.4, -160.6, -154.7)]
_COORD_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


@dataclass
class CallTracker:
    """Counts external HTTP calls made while serving one request."""

    calls: int = 0
    cache_hits: int = 0
    log: list[str] = field(default_factory=list)

    def record(self, what: str) -> None:
        self.calls += 1
        self.log.append(what)


@dataclass(frozen=True)
class Location:
    lat: float
    lng: float
    label: str


@dataclass(frozen=True)
class Route:
    coords: list[tuple[float, float]]  # (lat, lng) per vertex, full resolution
    distance_miles: float
    duration_seconds: float


def in_usa(lat: float, lng: float) -> bool:
    return any(a <= lat <= b and c <= lng <= d for a, b, c, d in US_BOXES)


def _cache_key(prefix: str, raw: str) -> str:
    return f"{prefix}:{hashlib.sha1(raw.strip().lower().encode()).hexdigest()}"


def _http_get(url: str, tracker: CallTracker, what: str, **kwargs) -> requests.Response:
    tracker.record(what)
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": settings.EXTERNAL_USER_AGENT},
            timeout=settings.EXTERNAL_TIMEOUT_SECONDS,
            **kwargs,
        )
    except requests.RequestException as exc:
        logger.warning("External call failed (%s): %s", what, exc)
        raise UpstreamError(f"Could not reach the {what} service. Please retry shortly.") from exc
    if resp.status_code >= 500 or resp.status_code == 429:
        raise UpstreamError(f"The {what} service is unavailable (HTTP {resp.status_code}).")
    return resp


def resolve_location(text: str, tracker: CallTracker) -> Location:
    """Turn user input ("lat,lng" or free text) into a US coordinate."""
    if not text or not text.strip():
        raise InvalidLocation("Location must not be empty.")

    if m := _COORD_RE.match(text):
        lat, lng = float(m.group(1)), float(m.group(2))
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise InvalidLocation(f"Coordinates out of range: {text!r}.")
        loc = Location(lat, lng, f"{lat:.5f},{lng:.5f}")
    else:
        key = _cache_key("geo", text)
        cached = cache.get(key)
        if cached:
            tracker.cache_hits += 1
            loc = cached
        else:
            resp = _http_get(
                f"{settings.NOMINATIM_BASE_URL}/search",
                tracker,
                "geocoding",
                params={"q": text, "format": "jsonv2", "limit": 1, "countrycodes": "us"},
            )
            results = resp.json() if resp.ok else []
            if not results:
                raise InvalidLocation(f"Could not find a US location matching {text!r}.")
            top = results[0]
            loc = Location(float(top["lat"]), float(top["lon"]), top.get("display_name", text))
            cache.set(key, loc, settings.CACHE_TTL_SECONDS)

    if not in_usa(loc.lat, loc.lng):
        raise OutsideUSA(f"{text!r} is not inside the USA.")
    return loc


def fetch_route(start: Location, end: Location, tracker: CallTracker) -> Route:
    """ONE OSRM call returning the full driving geometry."""
    key = _cache_key("route", f"{start.lat:.5f},{start.lng:.5f};{end.lat:.5f},{end.lng:.5f}")
    cached = cache.get(key)
    if cached:
        tracker.cache_hits += 1
        return cached

    coords = f"{start.lng},{start.lat};{end.lng},{end.lat}"
    resp = _http_get(
        f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}",
        tracker,
        "routing",
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
    )
    data = resp.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise NoRouteFound(
            f"No drivable route between the two locations ({data.get('code', 'unknown')})."
        )
    best = data["routes"][0]
    route = Route(
        coords=[(lat, lng) for lng, lat in best["geometry"]["coordinates"]],
        distance_miles=best["distance"] / METERS_PER_MILE,
        duration_seconds=best["duration"],
    )
    cache.set(key, route, settings.CACHE_TTL_SECONDS)
    return route
