"""Health-check endpoints."""

from fastapi import APIRouter

from memlite.common.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return basic service health status."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
    }


@router.get("/version")
def version() -> dict[str, str]:
    """Return basic service version information."""
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": "0.1.0",
    }
