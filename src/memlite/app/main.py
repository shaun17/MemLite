"""Application entrypoint for MemLite."""

import uvicorn
from fastapi import FastAPI

from memlite.api.health import router as health_router
from memlite.api.metrics import router as metrics_router
from memlite.app.resources import ResourceManager
from memlite.common.config import get_settings
from memlite.common.logging import configure_logging


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, description="MemLite API")
    app.state.resources = ResourceManager.create(settings)
    app.include_router(health_router)
    app.include_router(metrics_router)
    return app


app = create_app()


def main() -> None:
    """Run the development server."""
    settings = get_settings()
    uvicorn.run(
        "memlite.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
