from fastapi.testclient import TestClient

from memolite.app.main import create_app
from memolite.common.config import reset_settings_cache


def test_metrics_endpoint_returns_snapshot(tmp_path, monkeypatch):
    monkeypatch.setenv("MEMOLITE_SQLITE_PATH", str(tmp_path / "memolite.sqlite3"))
    monkeypatch.setenv("MEMOLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()
    app = create_app()
    app.state.resources.metrics.increment("requests", 2)
    app.state.resources.metrics.observe_timing("search_latency_ms", 12.5)
    with TestClient(app) as client:
        response = client.get("/metrics")

    assert response.status_code == 200
    assert response.json()["counters"]["requests"] == 2
    assert response.json()["timings_ms"]["search_latency_ms"]["last"] == 12.5
