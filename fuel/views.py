from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import FuelStation
from .serializers import RouteRequestSerializer
from .services.errors import RoutePlanningError
from .services.planner import TripResult, plan_trip

SIMPLIFY_EVERY_MILES = 2.0


def _geometry(result: TripResult, mode: str) -> dict:
    coords = result.route.coords
    if mode == "simplified" and len(coords) > 2:
        # keep roughly one vertex per SIMPLIFY_EVERY_MILES using index spacing
        step = max(1, round(len(coords) / max(2, result.route.distance_miles / SIMPLIFY_EVERY_MILES)))
        picked = coords[::step]
        if picked[-1] != coords[-1]:
            picked.append(coords[-1])
        coords = picked
    # GeoJSON order is [lng, lat]
    return {"type": "LineString", "coordinates": [[round(lng, 5), round(lat, 5)] for lat, lng in coords]}


def _place(loc) -> dict:
    return {"query": None, "lat": loc.lat, "lng": loc.lng, "label": loc.label}


def build_payload(result: TripResult, geometry: str) -> dict:
    miles_per_gallon = settings.VEHICLE_MPG
    stops, origin_fill, order = [], None, 0
    for p in result.plan.purchases:
        entry = {
            "gallons": round(p.gallons, 3),
            "cost": str(p.cost),
            "mile_marker": round(p.candidate.mile, 1),
            "price_per_gallon": f"{p.candidate.price:.4f}",
        }
        station = p.candidate.ref
        if station is None:  # the estimated fill-up at the origin
            origin_fill = {
                **entry,
                "note": "No listed station at the start; priced at the average of stations "
                f"within 100 miles of it (${p.candidate.price:.4f}/gal).",
            }
            continue
        order += 1
        stops.append(
            {
                "order": order,
                "name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "location": {"lat": round(station.lat, 5), "lng": round(station.lng, 5)},
                **entry,
            }
        )

    return {
        "start": _place(result.start),
        "finish": _place(result.end),
        "route": {
            "distance_miles": round(result.route.distance_miles, 1),
            "duration_hours": round(result.route.duration_seconds / 3600, 2),
            "geometry": _geometry(result, geometry),
        },
        "fuel_stops": stops,
        "origin_fill_up": origin_fill,
        "summary": {
            "total_fuel_cost": str(result.plan.total_cost),
            "total_gallons": round(result.plan.total_gallons, 3),
            "average_price_per_gallon": (
                f"{(result.plan.total_cost / Decimal(str(result.plan.total_gallons))):.4f}"
                if result.plan.total_gallons
                else None
            ),
            "number_of_fuel_stops": len(stops),
            "vehicle": {"range_miles": settings.VEHICLE_RANGE_MILES, "mpg": miles_per_gallon},
            "currency": "USD",
        },
        "meta": {
            "external_api_calls": result.tracker.calls,
            "external_calls_detail": result.tracker.log,
            "cache_hits": result.tracker.cache_hits,
            "stations_considered": result.candidates_considered,
            "timings_ms": result.timings_ms,
        },
    }


class RouteView(APIView):
    """Plan a route and the cheapest fuel stops along it."""

    authentication_classes: list = []
    permission_classes: list = []

    @extend_schema(
        request=RouteRequestSerializer,
        responses={200: dict, 400: dict, 422: dict, 502: dict},
        summary="Route + optimal fuel stops",
    )
    def post(self, request):
        return self._handle(request.data)

    @extend_schema(
        parameters=[
            OpenApiParameter("start", str, required=True),
            OpenApiParameter("finish", str, required=True),
            OpenApiParameter("geometry", str, enum=["simplified", "full"]),
        ],
        responses={200: dict, 400: dict, 422: dict, 502: dict},
        summary="Same as POST, using query parameters (handy for the map page)",
    )
    def get(self, request):
        return self._handle(request.query_params)

    def _handle(self, data):
        ser = RouteRequestSerializer(data=data)
        ser.is_valid(raise_exception=True)
        try:
            result = plan_trip(ser.validated_data["start"], ser.validated_data["finish"])
        except RoutePlanningError as exc:
            return Response({"error": {"code": exc.code, "message": exc.message}}, status=exc.status)
        payload = build_payload(result, ser.validated_data["geometry"])
        payload["start"]["query"] = ser.validated_data["start"]
        payload["finish"]["query"] = ser.validated_data["finish"]
        return Response(payload)


def health(_request):
    return JsonResponse({"status": "ok", "stations_loaded": FuelStation.objects.count()})


def map_page(request):
    return render(request, "fuel/map.html")
