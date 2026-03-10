"""Application entrypoint for MemLite."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from memolite.api.health import router as health_router
from memolite.api.memory_config import router as memory_config_router
from memolite.api.memories import router as memories_router
from memolite.api.metrics import router as metrics_router
from memolite.api.projects import router as projects_router
from memolite.api.semantic_config import router as semantic_config_router
from memolite.api.semantic_features import router as semantic_features_router
from memolite.api.sessions import router as sessions_router
from memolite.app.resources import ResourceManager
from memolite.common.config import get_settings
from memolite.common.logging import RequestLoggingMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and close app-scoped resources."""
    resources: ResourceManager = app.state.resources
    await resources.initialize()
    yield
    await resources.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(title=settings.app_name, description="MemLite API", lifespan=lifespan)
    app.state.resources = ResourceManager.create(settings)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(projects_router)
    app.include_router(sessions_router)
    app.include_router(memories_router)
    app.include_router(memory_config_router)
    app.include_router(semantic_features_router)
    app.include_router(semantic_config_router)
    return app


app = create_app()


def main() -> None:
    """Run the development server."""
    settings = get_settings()
    uvicorn.run(
        "memolite.app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )
