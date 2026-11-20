import numpy as np
import pytest

from fuel.services.geodata import normalize_place, read_price_csv
from fuel.services.spatial import build_profile, haversine_miles, stations_along_route


def test_haversine_known_distance():
    # New York -> Los Angeles is ~2,445 great-circle miles
    d = haversine_miles(40.7128, -74.0060, 34.0522, -118.2437)
    assert 2430 < float(d) < 2460


def test_profile_scales_to_router_distance():
    coords = [(40.0, -100.0), (40.0, -99.0), (40.0, -98.0)]
    prof = build_profile(coords, official_miles=200.0)
    assert prof.total_miles == pytest.approx(200.0)
    assert prof.cum_miles[1] == pytest.approx(100.0)


def test_stations_near_route_only_with_mile_marker():
    coords = [(40.0, -100.0 + i * 0.05) for i in range(200)]  # ~1,000 mile line, -100 -> -90
    prof = build_profile(coords, official_miles=1000.0)
    st_lat = np.array([40.02, 40.5, 45.0, 40.0])
    st_lng = np.array([-95.0, -95.0, -95.0, -80.0])
    idx, miles, off = stations_along_route(prof, st_lat, st_lng, max_offset_miles=5)
    assert list(idx) == [0]  # 40.5N is ~35 mi off, 45N is far, -80 is beyond the route end
    assert 490 < miles[0] < 510  # 5 of 10 degrees ~ half the route
    assert off[0] < 5


def test_normalize_place_variants():
    assert normalize_place("St. Louis") == "saint louis"
    assert normalize_place("Mc Calla") == "mccalla"
    assert normalize_place("Augusta-Richmond (balance)") == "augusta richmond"


def test_csv_cleaning(tmp_path):
    csv_file = tmp_path / "p.csv"
    csv_file.write_text(
        "OPIS Truckstop ID,Truckstop Name,Address,City,State,Rack ID,Retail Price\n"
        '1,A,"I-1",Tomah   ,WI,1,3.50\n'
        '1,A2,"I-1",Tomah,WI,1,3.40\n'  # duplicate id: cheaper wins
        '2,Canadian,"X",Calgary,AB,1,1.20\n'  # non-US dropped
        '3,B,"I-2",Waco,TX,1,3.10\n',
        encoding="utf-8",
    )
    records, stats = read_price_csv(csv_file)
    assert {r.truckstop_id: str(r.price) for r in records} == {1: "3.4000", 3: "3.1000"}
    assert stats["non_us"] == 1 and stats["duplicates"] == 1
    assert next(r for r in records if r.truckstop_id == 1).city == "Tomah"
