import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from memlite.app.main import create_app
from memlite.common.config import reset_settings_cache


def test_project_routes_crud_and_episode_count(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMLITE_SQLITE_PATH", str(tmp_path / "memlite.sqlite3"))
    monkeypatch.setenv("MEMLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()

    with TestClient(create_app()) as client:
        response = client.post(
            "/projects",
            json={"org_id": "org-a", "project_id": "project-a", "description": "demo"},
        )
        assert response.status_code == 200

        project = client.get("/projects/org-a/project-a")
        listed = client.get("/projects", params={"org_id": "org-a"})
        count = client.get("/projects/org-a/project-a/episodes/count")

        assert project.status_code == 200
        assert project.json()["project_id"] == "project-a"
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert count.json()["count"] == 0


def test_memory_routes_add_search_list_and_delete(tmp_path: Path, monkeypatch):
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
        add = client.post(
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
        search = client.post(
            "/memories/search",
            json={
                "query": "food ramen",
                "session_key": "session-a",
                "session_id": "session-a",
                "semantic_set_id": "session-a",
            },
        )
        listed = client.get("/memories", params={"session_key": "session-a"})
        deleted = client.request(
            "DELETE",
            "/memories/episodes",
            json={"episode_uids": ["ep-1"], "semantic_set_id": "session-a"},
        )
        searched_after = client.post(
            "/memories/search",
            json={
                "query": "food ramen",
                "session_key": "session-a",
                "session_id": "session-a",
            },
        )

        assert add.status_code == 200
        assert search.status_code == 200
        assert search.json()["episodic_matches"][0]["episode"]["uid"] == "ep-1"
        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert deleted.status_code == 200
        assert searched_after.json()["episodic_matches"] == []


def test_semantic_feature_routes_crud(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMLITE_SQLITE_PATH", str(tmp_path / "memlite.sqlite3"))
    monkeypatch.setenv("MEMLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()

    with TestClient(create_app()) as client:
        created = client.post(
            "/semantic/features",
            json={
                "set_id": "set-a",
                "category": "profile",
                "tag": "food",
                "feature_name": "favorite_food",
                "value": "ramen",
                "embedding": [1.0, 0.0, 0.0, 0.0],
            },
        )
        feature_id = created.json()["id"]
        fetched = client.get(f"/semantic/features/{feature_id}")
        updated = client.patch(
            f"/semantic/features/{feature_id}",
            json={"value": "soba"},
        )
        fetched_after = client.get(f"/semantic/features/{feature_id}")

        assert created.status_code == 200
        assert fetched.status_code == 200
        assert fetched.json()["value"] == "ramen"
        assert updated.status_code == 200
        assert fetched_after.json()["value"] == "soba"
