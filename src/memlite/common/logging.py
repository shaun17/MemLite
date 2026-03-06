"""Logging setup for MemLite."""

import logging
from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from memlite.common.config import Settings

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(settings: Settings) -> None:
    """Configure root logging for the application."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=_LOG_FORMAT,
        force=True,
    )
    logging.getLogger("aiosqlite").setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log access and error paths for HTTP requests."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        logger = logging.getLogger("memlite.http")
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (perf_counter() - started) * 1000
            logger.exception(
                "request failed method=%s path=%s duration_ms=%.3f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (perf_counter() - started) * 1000
        logger.info(
            "request method=%s path=%s status=%s duration_ms=%.3f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        metrics = getattr(request.app.state.resources, "metrics", None)
        if metrics is not None:
            metrics.increment("http_requests_total")
            metrics.observe_timing("http_request_duration_ms", duration_ms)
        return response
