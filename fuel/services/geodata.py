"""Offline helpers that turn the price CSV into located stations.

The CSV has no coordinates, so each station is placed at the centroid of its
city using the US Census Gazetteer (a free public dataset bundled in ``data/``).
Doing this once at load time means a request never needs a geocoding API call.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ "
    "NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)

_SUFFIX = re.compile(
    r"\s+(city and borough|consolidated government|metropolitan government|unified government"
    r"|urban county|municipality|township|plantation|borough|village|town|city|cdp|ccd)$",
    re.IGNORECASE,
)


def normalize_place(name: str) -> str:
    """Lower-case a place name and smooth over punctuation/abbreviation quirks."""
    s = re.sub(r"\s*\(.*?\)", "", name.lower().strip())
    s = s.replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\bst\b", "saint", s)
    s = re.sub(r"\bft\b", "fort", s)
    s = re.sub(r"\bmt\b", "mount", s)
    s = re.sub(r"\bmc ", "mc", s)  # "Mc Calla" -> "mccalla"
    return re.sub(r"\s+", " ", s).strip()


@dataclass(frozen=True)
class Place:
    lat: float
    lng: float


class Gazetteer:
    """(state, place name) -> city centroid.

    Files are loaded in priority order (incorporated places first, then county
    subdivisions such as townships), and the first entry for a name wins.
    Unmatched cities return ``None`` and are skipped rather than mis-located.
    """

    def __init__(self) -> None:
        self._index: dict[tuple[str, str], Place] = {}

    def add_file(self, path: Path) -> None:
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="	"):
                row = {k.strip(): (v or "").strip() for k, v in row.items()}
                state, raw = row["USPS"], row["NAME"]
                place = Place(float(row["INTPTLAT"]), float(row["INTPTLONG"]))
                once = _SUFFIX.sub("", raw)  # "Dodge City city" -> "Dodge City"
                full = once
                while (nxt := _SUFFIX.sub("", full)) != full:  # -> "Dodge"
                    full = nxt
                for variant in (once, raw, full):  # most specific key first
                    self._index.setdefault((state, normalize_place(variant)), place)

    @classmethod
    def from_files(cls, *paths: Path) -> Gazetteer:
        gaz = cls()
        for path in paths:
            gaz.add_file(path)
        return gaz

    def locate(self, city: str, state: str) -> Place | None:
        return self._index.get((state, normalize_place(city)))


@dataclass(frozen=True)
class StationRecord:
    truckstop_id: int
    name: str
    address: str
    city: str
    state: str
    price: Decimal


def read_price_csv(path: Path) -> tuple[list[StationRecord], dict[str, int]]:
    """Parse + clean the CSV. Returns (unique stations, stats).

    * Whitespace is stripped (city names are space-padded in the source).
    * Non-US rows (Canadian provinces) are dropped.
    * The file repeats some truckstop IDs with different prices; we keep the
      lowest listed price per ID.
    """
    stats = {"rows": 0, "non_us": 0, "bad_rows": 0, "duplicates": 0}
    best: dict[int, StationRecord] = {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            stats["rows"] += 1
            state = row["State"].strip().upper()
            if state not in US_STATES:
                stats["non_us"] += 1
                continue
            try:
                rec = StationRecord(
                    truckstop_id=int(row["OPIS Truckstop ID"]),
                    name=row["Truckstop Name"].strip(),
                    address=row["Address"].strip(),
                    city=row["City"].strip(),
                    state=state,
                    price=Decimal(row["Retail Price"]).quantize(Decimal("0.0001")),
                )
            except (ValueError, ArithmeticError):
                stats["bad_rows"] += 1
                continue
            prev = best.get(rec.truckstop_id)
            if prev is not None:
                stats["duplicates"] += 1
                if prev.price <= rec.price:
                    continue
            best[rec.truckstop_id] = rec
    return list(best.values()), stats
