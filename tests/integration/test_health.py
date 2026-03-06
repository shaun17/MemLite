from fastapi.testclient import TestClient

from memlite.app.main import create_app
from memlite.common.config import reset_settings_cache


def test_health_endpoint_returns_ok():
    reset_settings_cache()
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
