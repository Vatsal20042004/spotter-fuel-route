"""OpenAPI documentation fragments (examples and parameter help) for the route endpoint."""

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse

PARAMETERS = [
    OpenApiParameter(
        "start",
        str,
        required=True,
        examples=[
            OpenApiExample("City and state", value="New York, NY"),
            OpenApiExample("Coordinates", value="40.7128,-74.0060"),
        ],
        description='Where the trip starts: "City, ST" (e.g. "Austin, TX") or "lat,lng". Must be in the USA.',
    ),
    OpenApiParameter(
        "finish",
        str,
        required=True,
        examples=[
            OpenApiExample("City and state", value="Los Angeles, CA"),
            OpenApiExample("Coordinates", value="34.0522,-118.2437"),
        ],
        description='Where the trip ends: "City, ST" or "lat,lng". Must be in the USA.',
    ),
    OpenApiParameter(
        "range_miles",
        float,
        required=False,
        examples=[OpenApiExample("Default", value=500)],
        description="Vehicle range on a full tank, in miles (50 to 2000). Default 500.",
    ),
    OpenApiParameter(
        "mpg",
        float,
        required=False,
        examples=[OpenApiExample("Default", value=10)],
        description="Fuel economy in miles per gallon (1 to 100). Default 10.",
    ),
    OpenApiParameter(
        "geometry",
        str,
        required=False,
        enum=["simplified", "full"],
        description="'simplified' (default) keeps the response small; 'full' returns every route vertex.",
    ),
]

REQUEST_EXAMPLES = [
    OpenApiExample(
        "New York to Los Angeles",
        request_only=True,
        value={"start": "New York, NY", "finish": "Los Angeles, CA"},
    ),
    OpenApiExample(
        "Custom vehicle (350 mi range, 6.5 mpg)",
        request_only=True,
        value={"start": "Dallas, TX", "finish": "Atlanta, GA", "range_miles": 350, "mpg": 6.5},
    ),
    OpenApiExample(
        "Coordinates (exactly one map call)",
        request_only=True,
        value={"start": "25.7617,-80.1918", "finish": "47.6062,-122.3321"},
    ),
]

SUCCESS_EXAMPLE = OpenApiExample(
    "Abridged success response",
    response_only=True,
    status_codes=["200"],
    value={
        "start": {"query": "Chicago, IL", "lat": 41.83, "lng": -87.68, "label": "Chicago, IL"},
        "finish": {"query": "Denver, CO", "lat": 39.76, "lng": -104.88, "label": "Denver, CO"},
        "route": {
            "distance_miles": 1003.0,
            "duration_hours": 15.2,
            "geometry": {"type": "LineString", "coordinates": [[-87.68, 41.83], "..."]},
        },
        "fuel_stops": [
            {
                "order": 2,
                "name": "QUIKTRIP #7208",
                "city": "Bellwood",
                "state": "IL",
                "location": {"lat": 41.88, "lng": -87.88},
                "detour_miles": 0.9,
                "mile_marker": 13.0,
                "price_per_gallon": "3.0790",
                "gallons": 30.9,
                "cost": "95.16",
            }
        ],
        "origin_fill_up": {
            "gallons": 1.0,
            "cost": "3.40",
            "note": "Estimated: no listed station at the start.",
        },
        "summary": {
            "total_fuel_cost": "298.43",
            "total_gallons": 100.3,
            "number_of_fuel_stops": 4,
            "vehicle": {"range_miles": 500.0, "mpg": 10.0},
            "currency": "USD",
        },
        "savings": {"price_blind": {"baseline_cost": "342.39", "you_save": "43.96", "percent": 12.8}},
        "meta": {"external_api_calls": 1, "cache_hits": 0, "timings_ms": {"total_ms": 1008.7}},
    },
)

ERROR_EXAMPLE = OpenApiExample(
    "Outside the USA",
    response_only=True,
    status_codes=["400"],
    value={"error": {"code": "outside_usa", "message": "'48.8566,2.3522' is not inside the USA."}},
)

RESPONSES = {
    200: OpenApiResponse(description="Route, fuel stops, total cost and savings.", response=dict),
    400: OpenApiResponse(description="Bad input, or a location outside the USA.", response=dict),
    422: OpenApiResponse(
        description="No drivable route, or a gap longer than the vehicle range with no fuel station.",
        response=dict,
    ),
    502: OpenApiResponse(description="The free map service was unavailable. Retry shortly.", response=dict),
}
