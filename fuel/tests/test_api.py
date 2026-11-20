"""API contract tests. External services are mocked, so they are fast and offline."""

from unittest import mock

import pytest
from django.core.cache import cache
from django.urls import reverse

from fuel.models import FuelStation
from fuel.services.planner import StationIndex

# A straight ~1,000 mile west-east line at 40N (lng -110 -> -92).
LINE = [[-110.0 + i * 0.1, 40.0] for i in range(181)]
OSRM_OK = {
    "code": "Ok",
    "routes": [{"distance": 1_000 * 1609.344, "duration": 14 * 3600, "geometry": {"coordinates": LINE}}],
}


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload, self.status_code = payload, status
        self.ok = status < 400

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _clean_state(db):
    cache.clear()
    StationIndex.reset()
    yield
    StationIndex.reset()


@pytest.fixture
def stations(db):
    rows = [
        ("A", "Start Town", "CO", 40.0, -109.95, "3.50"),
        ("B", "Middle Town", "NE", 40.0, -101.0, "3.00"),
        ("C", "Late Town", "NE", 40.0, -95.0, "3.40"),
    ]
    for i, (name, city, st, lat, lng, price) in enumerate(rows, 1):
        FuelStation.objects.create(
            truckstop_id=i, name=name, address="I-80", city=city, state=st, price=price, lat=lat, lng=lng
        )


def post(client, **body):
    return client.post(reverse("route"), body, content_type="application/json")


def test_coordinates_use_exactly_one_external_call(client, stations):
    with mock.patch("requests.get", return_value=FakeResponse(OSRM_OK)) as get:
        resp = post(client, start="40.0,-110.0", finish="40.0,-92.0")
    assert resp.status_code == 200
    body = resp.json()
    assert get.call_count == 1
    assert body["meta"]["external_api_calls"] == 1
    assert body["route"]["geometry"]["type"] == "LineString"
    assert body["summary"]["vehicle"] == {"range_miles": 500.0, "mpg": 10.0}


def test_cost_matches_sum_of_stops_and_gallons(client, stations):
    with mock.patch("requests.get", return_value=FakeResponse(OSRM_OK)):
        body = post(client, start="40.0,-110.0", finish="40.0,-92.0").json()
    stops = body["fuel_stops"]
    origin = body["origin_fill_up"]
    spent = sum(float(s["cost"]) for s in stops) + (float(origin["cost"]) if origin else 0)
    assert float(body["summary"]["total_fuel_cost"]) == pytest.approx(spent, abs=0.01)
    gallons = sum(s["gallons"] for s in stops) + (origin["gallons"] if origin else 0)
    assert gallons == pytest.approx(body["route"]["distance_miles"] / 10, rel=1e-3)
    assert stops == sorted(stops, key=lambda s: s["mile_marker"])


def test_repeat_request_is_served_from_cache(client, stations):
    with mock.patch("requests.get", return_value=FakeResponse(OSRM_OK)) as get:
        post(client, start="40.0,-110.0", finish="40.0,-92.0")
        second = post(client, start="40.0,-110.0", finish="40.0,-92.0").json()
    assert get.call_count == 1
    assert second["meta"]["external_api_calls"] == 0 and second["meta"]["cache_hits"] == 1


def test_addresses_use_at_most_three_calls(client, stations):
    geo = lambda lat, lon: FakeResponse([{"lat": str(lat), "lon": str(lon), "display_name": "x"}])  # noqa: E731
    responses = [geo(40.0, -110.0), geo(40.0, -92.0), FakeResponse(OSRM_OK)]
    with mock.patch("requests.get", side_effect=responses) as get:
        body = post(client, start="Town A, CO", finish="Town B, NE").json()
    assert get.call_count == 3 and body["meta"]["external_api_calls"] == 3


def test_rejects_location_outside_usa(client, stations):
    resp = post(client, start="48.8566,2.3522", finish="40.0,-92.0")  # Paris
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "outside_usa"


def test_validation_errors(client, stations):
    assert post(client, start="40.0,-110.0").status_code == 400
    assert post(client, start="40.0,-110.0", finish="40.0,-110.0").status_code == 400


def test_upstream_failure_maps_to_502(client, stations):
    with mock.patch("requests.get", return_value=FakeResponse({}, status=503)):
        resp = post(client, start="40.0,-110.0", finish="40.0,-92.0")
    assert resp.status_code == 502


def test_no_route_maps_to_422(client, stations):
    with mock.patch("requests.get", return_value=FakeResponse({"code": "NoRoute"})):
        resp = post(client, start="40.0,-110.0", finish="40.0,-92.0")
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "no_route"


def test_infeasible_when_gap_exceeds_range(client, db):
    FuelStation.objects.create(
        truckstop_id=1, name="Lonely", address="x", city="T", state="NE", price="3.0", lat=40.0, lng=-108.0
    )
    with mock.patch("requests.get", return_value=FakeResponse(OSRM_OK)):
        resp = post(client, start="40.0,-110.0", finish="40.0,-92.0")
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "no_feasible_fuel_plan"


def test_health_and_map_page(client, stations):
    assert client.get(reverse("health")).json() == {"status": "ok", "stations_loaded": 3}
    assert client.get("/").status_code == 200
