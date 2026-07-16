"""In-memory rate limiting middleware.

Uses a Python dict for per-client-IP request counting within a sliding
minute window.  No external dependencies (no Redis, no slowapi).

Implemented as pure ASGI middleware for maximum compatibility across
Starlette / FastAPI versions.
"""

import logging
import re
import time
from collections import defaultdict
from typing import Dict, Tuple

from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Format:  {client_ip: [(timestamp, ...), ...]}
# Each entry is a list of epoch-second timestamps for requests.
_window: Dict[str, list] = defaultdict(list)

# Per-endpoint overrides: prefix -> (max_requests, window_seconds)
_endpoint_limits: Dict[str, Tuple[int, int]] = {}


def _parse_limit(limit_str: str) -> Tuple[int, int]:
    """Parse a limit string like '100/minute' -> (100, 60)."""
    m = re.match(r"^(\d+)\s*/\s*(minute|second|hour|day)$", limit_str)
    if not m:
        raise ValueError(f"Invalid rate limit format: {limit_str!r}")
    count = int(m.group(1))
    unit = m.group(2)
    multiplier = {
        "second": 1,
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    return count, multiplier[unit]


class RateLimitMiddleware:
    """Pure-ASGI middleware that enforces per-IP rate limits.

    Limits are configured via ``_endpoint_limits`` (prefix-based) and a
    global default.  Set ``app.state.rate_limit_enabled = False`` to
    disable at runtime.

    Usage in FastAPI::

        app.add_middleware(RateLimitMiddleware, default_limit="100/minute")
        RateLimitMiddleware.set_endpoint_limit("/api/admin", "20/minute")
        app.state.rate_limit_enabled = True
    """

    def __init__(self, app, default_limit: str = "100/minute"):
        self.app = app
        self._max, self._window_sec = _parse_limit(default_limit)
        logger.info(
            "RateLimitMiddleware initialized: %d requests per %ds (global)",
            self._max, self._window_sec,
        )

    @classmethod
    def set_endpoint_limit(cls, prefix: str, limit_str: str):
        """Register a per-endpoint limit.

        Example:
            RateLimitMiddleware.set_endpoint_limit("/api/admin", "20/minute")
        """
        _endpoint_limits[prefix] = _parse_limit(limit_str)

    async def __call__(self, scope, receive, send):
        # Only handle HTTP requests
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Allow runtime disable via app.state.rate_limit_enabled
        fastapi_app = scope.get("app")
        if fastapi_app is not None and not getattr(fastapi_app.state, "rate_limit_enabled", True):
            await self.app(scope, receive, send)
            return

        # Determine which limit applies
        max_req = self._max
        window = self._window_sec
        path = scope.get("path", "/")
        for prefix, (cnt, sec) in _endpoint_limits.items():
            if path.startswith(prefix):
                max_req = cnt
                window = sec
                break

        # Extract client IP
        client_ip = _get_client_ip_from_scope(scope)
        now = time.time()
        cutoff = now - window

        # Clean old entries and check limit
        bucket = _window[client_ip]
        bucket[:] = [t for t in bucket if t > cutoff]

        if len(bucket) >= max_req:
            retry_after = int(bucket[0] + window - now) + 1
            logger.warning(
                "Rate limit hit: ip=%s path=%s count=%d/%d retry_after=%ds",
                client_ip, path, len(bucket), max_req, retry_after,
            )
            response = JSONResponse(
                {"detail": "Too Many Requests", "retry_after": retry_after},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        bucket.append(now)
        await self.app(scope, receive, send)


def _get_client_ip_from_scope(scope) -> str:
    """Extract client IP from ASGI scope."""
    # Check X-Forwarded-For header
    for header_name, header_value in scope.get("headers", []):
        if header_name == b"x-forwarded-for":
            return header_value.decode("latin-1").split(",")[0].strip()

    # Fall back to client address
    client = scope.get("client")
    if client:
        return client[0]  # (host, port) tuple

    return "unknown"


def periodic_cleanup():
    """Remove entries for IPs that have no recent requests.

    Call from a background thread if the dict grows too large.
    """
    now = time.time()
    stale_ips = []
    for ip, bucket in _window.items():
        if not bucket or all(t < now - 600 for t in bucket):
            stale_ips.append(ip)
    for ip in stale_ips:
        del _window[ip]
    if stale_ips:
        logger.debug("Rate-limit cleanup: removed %d stale IP entries", len(stale_ips))
