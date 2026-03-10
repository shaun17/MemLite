import logging
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from memolite.common.config import Settings
from memolite.common.logging import RequestLoggingMiddleware, configure_logging
from memolite.metrics.service import MetricsService


def test_configure_logging_sets_root_level():
    settings = Settings(log_level="DEBUG")

    configure_logging(settings)

    assert logging.getLogger().level == logging.DEBUG


def test_request_logging_middleware_logs_access(caplog):
    app = FastAPI()
    app.state.resources = SimpleNamespace(metrics=MetricsService())
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    with caplog.at_level(logging.INFO, logger="memolite.http"):
        with TestClient(app) as client:
            response = client.get("/ok")

    assert response.status_code == 200
    assert "request method=GET path=/ok status=200" in caplog.text


def test_request_logging_middleware_logs_errors(caplog):
    app = FastAPI()
    app.state.resources = SimpleNamespace(metrics=MetricsService())
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/boom")
    def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    with caplog.at_level(logging.ERROR, logger="memolite.http"):
        with pytest.raises(RuntimeError, match="boom"):
            with TestClient(app) as client:
                client.get("/boom")

    assert "request failed method=GET path=/boom" in caplog.text
