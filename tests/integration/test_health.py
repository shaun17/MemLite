from fastapi.testclient import TestClient

from memolite.app.main import create_app
from memolite.common.config import reset_settings_cache


def test_health_endpoint_returns_ok(monkeypatch, tmp_path):
    monkeypatch.setenv("MEMOLITE_SQLITE_PATH", str(tmp_path / "memolite.sqlite3"))
    monkeypatch.setenv("MEMOLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
