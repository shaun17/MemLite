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


def test_semantic_config_routes_and_version(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMLITE_SQLITE_PATH", str(tmp_path / "memlite.sqlite3"))
    monkeypatch.setenv("MEMLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()

    with TestClient(create_app()) as client:
        set_type = client.post(
            "/semantic/config/set-types",
            json={
                "org_id": "org-a",
                "metadata_tags_sig": "user_id|agent_id",
                "name": "default",
            },
        )
        set_type_id = set_type.json()["id"]
        set_config = client.post(
            "/semantic/config/sets",
            json={
                "set_id": "set-a",
                "set_type_id": set_type_id,
                "set_name": "Set A",
                "embedder_name": "default",
            },
        )
        category = client.post(
            "/semantic/config/categories",
            json={
                "set_id": "set-a",
                "name": "profile",
                "prompt": "profile prompt",
            },
        )
        category_id = category.json()["id"]
        template = client.post(
            "/semantic/config/category-templates",
            json={
                "set_type_id": set_type_id,
                "name": "profile-template",
                "category_name": "profile",
                "prompt": "template prompt",
            },
        )
        tag = client.post(
            "/semantic/config/tags",
            json={
                "category_id": category_id,
                "name": "food",
                "description": "Food preference",
            },
        )
        disabled = client.post(
            "/semantic/config/disabled-categories",
            json={"set_id": "set-a", "category_name": "profile"},
        )

        listed_set_types = client.get("/semantic/config/set-types", params={"org_id": "org-a"})
        fetched_set = client.get("/semantic/config/sets/set-a")
        listed_set_ids = client.get("/semantic/config/sets")
        fetched_category = client.get(f"/semantic/config/categories/{category_id}")
        category_set_ids = client.get("/semantic/config/categories/profile/set-ids")
        listed_templates = client.get(
            "/semantic/config/category-templates",
            params={"set_type_id": set_type_id},
        )
        listed_tags = client.get("/semantic/config/tags", params={"category_id": category_id})
        version = client.get("/version")

        assert set_type.status_code == 200
        assert set_config.status_code == 200
        assert category.status_code == 200
        assert template.status_code == 200
        assert tag.status_code == 200
        assert disabled.status_code == 200
        assert listed_set_types.status_code == 200
        assert listed_set_types.json()[0]["id"] == set_type_id
        assert fetched_set.json()["set_name"] == "Set A"
        assert listed_set_ids.json() == ["set-a"]
        assert fetched_category.json()["name"] == "profile"
        assert category_set_ids.json() == ["set-a"]
        assert listed_templates.json()[0]["name"] == "profile-template"
        assert listed_tags.json()[0]["name"] == "food"
        assert version.json()["version"] == "0.1.0"


def test_memory_config_routes_and_error_paths_and_openapi(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEMLITE_SQLITE_PATH", str(tmp_path / "memlite.sqlite3"))
    monkeypatch.setenv("MEMLITE_KUZU_PATH", str(tmp_path / "graph.kuzu"))
    reset_settings_cache()

    with TestClient(create_app()) as client:
        episodic = client.get("/memory-config/episodic")
        updated_episodic = client.patch(
            "/memory-config/episodic",
            json={"top_k": 8, "min_score": 0.2, "context_window": 2},
        )
        short_term = client.patch(
            "/memory-config/short-term",
            json={"message_capacity": 2048, "summary_enabled": False},
        )
        long_term = client.patch(
            "/memory-config/long-term",
            json={"semantic_enabled": True, "episodic_enabled": False},
        )
        missing_project = client.get("/projects/org-x/project-x")
        missing_feature = client.get("/semantic/features/9999")
        invalid_project = client.post("/projects", json={"org_id": "org-a"})
        openapi = client.get("/openapi.json")

        assert episodic.status_code == 200
        assert episodic.json()["top_k"] == 5
        assert updated_episodic.status_code == 200
        assert updated_episodic.json()["top_k"] == 8
        assert short_term.status_code == 200
        assert short_term.json()["message_capacity"] == 2048
        assert long_term.status_code == 200
        assert long_term.json()["episodic_enabled"] is False
        assert missing_project.status_code == 404
        assert missing_feature.status_code == 404
        assert invalid_project.status_code == 422
        assert openapi.status_code == 200
        assert "/projects" in openapi.json()["paths"]
