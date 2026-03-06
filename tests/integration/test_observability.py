import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from memlite.app.main import create_app
from memlite.common.config import reset_settings_cache


def test_search_path_emits_latency_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMLITE_SQLITE_PATH", str(tmp_path / "memlite.sqlite3"))
    monkeypatch.setenv("MEMLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()

    app = create_app()
    with TestClient(app) as client:
        client.post("/projects", json={"org_id": "org-a", "project_id": "project-a"})
        asyncio.run(
            app.state.resources.orchestrator.create_session(
                session_key="session-a",
                org_id="org-a",
                project_id="project-a",
                session_id="session-a",
                user_id="user-1",
            )
        )
        client.post(
            "/memories",
            json={
                "session_key": "session-a",
                "semantic_set_id": "session-a",
                "episodes": [
                    {
                        "uid": "ep-1",
                        "session_key": "session-a",
                        "session_id": "session-a",
                        "producer_id": "user-1",
                        "producer_role": "user",
                        "sequence_num": 1,
                        "content": "Ramen is my favorite food.",
                    }
                ],
            },
        )
        response = client.post(
            "/memories/search",
            json={
                "query": "favorite food",
                "session_key": "session-a",
                "session_id": "session-a",
            },
        )
        metrics = client.get("/metrics")

    assert response.status_code == 200
    payload = metrics.json()
    assert payload["counters"]["http_requests_total"] >= 1
    assert payload["counters"]["episodic_search_total"] >= 1
    assert payload["counters"]["vec_queries_total"] >= 1
    assert payload["counters"]["graph_queries_total"] >= 1
    assert payload["timings_ms"]["search_latency_ms"]["count"] >= 1
