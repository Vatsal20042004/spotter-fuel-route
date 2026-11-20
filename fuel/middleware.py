import logging
import time

logger = logging.getLogger("fuel.access")


class ResponseTimeMiddleware:
    """Adds an ``X-Response-Time-ms`` header and logs one line per API request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed = (time.perf_counter() - start) * 1000
        response["X-Response-Time-ms"] = f"{elapsed:.1f}"
        if request.path.startswith("/api/"):
            logger.info("%s %s -> %s in %.0f ms", request.method, request.path, response.status_code, elapsed)
        return response
