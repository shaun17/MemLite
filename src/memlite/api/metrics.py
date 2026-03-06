"""Metrics endpoints."""

from fastapi import APIRouter, Request

from memlite.app.resources import ResourceManager

router = APIRouter(tags=["system"])


@router.get("/metrics")
def metrics(request: Request) -> dict[str, object]:
    """Return bootstrap metrics snapshot."""
    resources: ResourceManager = request.app.state.resources
    return {
        "service": resources.settings.app_name,
        **resources.metrics.snapshot(),
    }
