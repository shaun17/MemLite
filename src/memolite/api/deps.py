"""API dependencies."""

from fastapi import Request

from memolite.app.resources import ResourceManager


def get_resources(request: Request) -> ResourceManager:
    """Return application resources from request state."""
    return request.app.state.resources
