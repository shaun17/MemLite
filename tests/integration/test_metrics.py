from fastapi.testclient import TestClient

from memlite.app.main import create_app
from memlite.common.config import reset_settings_cache


def test_metrics_endpoint_returns_snapshot():
    reset_settings_cache()
    app = create_app()
    app.state.resources.metrics.increment("requests", 2)
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json()["counters"]["requests"] == 2
