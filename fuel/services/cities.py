"""Offline "City, ST" lookup so common inputs need no geocoding API call at all.

Uses the same Census gazetteer that places the fuel stations. Anything that does not
parse as "City, State" or is not found falls back to Nominatim in ``routing.py``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from .geodata import US_STATES, Gazetteer, Place

STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}  # fmt: skip

_COUNTRY_TAIL = re.compile(r"[,\s]+(usa|us|u\.s\.a\.|u\.s\.|united states(?: of america)?)\.?$", re.I)


@lru_cache(maxsize=1)
def _places() -> Gazetteer:
    return Gazetteer.from_files(Path(settings.BASE_DIR) / "data" / "us_places_gazetteer_2023.txt")


def parse_city_state(text: str) -> tuple[str, str] | None:
    """'Austin, TX' / 'Austin, Texas' / 'Austin, TX, USA' -> ('Austin', 'TX'); else None."""
    cleaned = _COUNTRY_TAIL.sub("", text.strip())
    parts = [p.strip() for p in cleaned.split(",")]
    if len(parts) != 2 or not parts[0]:
        return None
    city, region = parts
    state = region.upper() if region.upper() in US_STATES else STATE_NAMES.get(region.lower())
    return (city, state) if state else None


def lookup_city(text: str) -> tuple[Place, str] | None:
    """Return (centroid, 'City, ST' label) for a US 'City, State' string, if known."""
    parsed = parse_city_state(text)
    if not parsed:
        return None
    city, state = parsed
    place = _places().locate(city, state)
    return (place, f"{city.title()}, {state}") if place else None
