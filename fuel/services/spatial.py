"""Find fuel stations near a route and place them at a mile marker along it.

Pure numpy. A coarse grid prefilter discards stations that are nowhere near the
route, then an exact haversine check runs only on the survivors, so a
cross-country route is matched against ~6k stations in a few milliseconds.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

EARTH_RADIUS_MILES = 3958.7613
GRID_DEG = 0.25  # ~17 miles; prefilter cell size
ROUTE_SAMPLE_MILES = 1.0  # route is resampled to roughly this spacing for matching


def haversine_miles(lat1, lng1, lat2, lng2):
    """Great-circle distance in miles; accepts scalars or broadcastable arrays."""
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dlmb = np.radians(lng2) - np.radians(lng1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


@dataclass(frozen=True)
class RouteProfile:
    """Route vertices with cumulative distance (miles) from the start."""

    lat: np.ndarray
    lng: np.ndarray
    cum_miles: np.ndarray

    @property
    def total_miles(self) -> float:
        return float(self.cum_miles[-1])


def build_profile(coords: list[tuple[float, float]], official_miles: float) -> RouteProfile:
    """Compute cumulative distance per vertex, scaled so the end equals the router's distance.

    Scaling keeps mile markers consistent with the distance the routing engine reports.
    """
    arr = np.asarray(coords, dtype=float)
    lat, lng = arr[:, 0], arr[:, 1]
    seg = haversine_miles(lat[:-1], lng[:-1], lat[1:], lng[1:]) if len(arr) > 1 else np.array([])
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if cum[-1] > 0 and official_miles > 0:
        cum *= official_miles / cum[-1]
    return RouteProfile(lat, lng, cum)


def _resample(profile: RouteProfile) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keep roughly one vertex per mile (always keeping the first and last)."""
    bins = np.floor(profile.cum_miles / ROUTE_SAMPLE_MILES).astype(np.int64)
    keep = np.concatenate([[True], bins[1:] != bins[:-1]])
    keep[-1] = True
    return profile.lat[keep], profile.lng[keep], profile.cum_miles[keep]


def _cells(lat: np.ndarray, lng: np.ndarray) -> np.ndarray:
    row = np.floor((lat + 90) / GRID_DEG).astype(np.int64)
    col = np.floor((lng + 180) / GRID_DEG).astype(np.int64)
    return row * 100_000 + col


def stations_along_route(
    profile: RouteProfile,
    st_lat: np.ndarray,
    st_lng: np.ndarray,
    max_offset_miles: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (station_indices, mile_markers, offsets) for stations within range of the route.

    ``mile_marker`` is the route distance at the route vertex closest to the station.
    """
    r_lat, r_lng, r_cum = _resample(profile)

    # 1) coarse prefilter: keep stations whose grid cell touches a cell the route passes through
    route_cells = np.unique(_cells(r_lat, r_lng))
    offsets = np.array([-100_001, -100_000, -99_999, -1, 0, 1, 99_999, 100_000, 100_001])
    neighbours = (route_cells[:, None] + offsets).ravel()
    maybe = np.flatnonzero(np.isin(_cells(st_lat, st_lng), neighbours))
    if maybe.size == 0:
        return maybe, np.array([]), np.array([])

    # 2) exact nearest-route-vertex distance for the survivors (chunked to bound memory)
    idx_out, mile_out, off_out = [], [], []
    chunk = max(1, 2_000_000 // max(1, r_lat.size))
    for s in range(0, maybe.size, chunk):
        part = maybe[s : s + chunk]
        d = haversine_miles(st_lat[part, None], st_lng[part, None], r_lat[None, :], r_lng[None, :])
        nearest = d.argmin(axis=1)
        offset = d[np.arange(part.size), nearest]
        ok = offset <= max_offset_miles
        idx_out.append(part[ok])
        mile_out.append(r_cum[nearest[ok]])
        off_out.append(offset[ok])
    return np.concatenate(idx_out), np.concatenate(mile_out), np.concatenate(off_out)
