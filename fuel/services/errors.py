class RoutePlanningError(Exception):
    """Base class; ``status`` is the HTTP status the API should answer with."""

    status = 400
    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidLocation(RoutePlanningError):
    status, code = 400, "invalid_location"


class OutsideUSA(RoutePlanningError):
    status, code = 400, "outside_usa"


class NoRouteFound(RoutePlanningError):
    status, code = 422, "no_route"


class NoFeasiblePlan(RoutePlanningError):
    status, code = 422, "no_feasible_fuel_plan"


class UpstreamError(RoutePlanningError):
    status, code = 502, "upstream_error"
