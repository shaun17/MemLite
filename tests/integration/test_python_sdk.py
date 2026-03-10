from pathlib import Path

import httpx
import pytest

from memlite.app.main import create_app
from memlite.app.resources import ResourceManager
from memlite.client import MemLiteClient
from memlite.common.config import Settings


async def _build_sdk_client(tmp_path: Path) -> tuple[MemLiteClient, ResourceManager]:
    app = create_app()
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    app.state.resources = resources
    await resources.initialize()
    transport = httpx.ASGITransport(app=app)
    client = MemLiteClient(base_url="http://testserver", transport=transport)
    return client, resources


@pytest.mark.anyio
async def test_sdk_client_context_manager(tmp_path: Path):
    client, resources = await _build_sdk_client(tmp_path)

    async with client as sdk:
        assert sdk.base_url == "http://testserver"

    await resources.close()


@pytest.mark.anyio
async def test_sdk_project_crud(tmp_path: Path):
    client, resources = await _build_sdk_client(tmp_path)

    await client.projects.create(
        org_id="org-a",
        project_id="project-a",
        description="demo",
    )
    project = await client.projects.get(org_id="org-a", project_id="project-a")
    projects = await client.projects.list(org_id="org-a")
    count = await client.projects.episode_count(org_id="org-a", project_id="project-a")
    await client.projects.delete(org_id="org-a", project_id="project-a")
    remaining = await client.projects.list(org_id="org-a")

    assert project.project_id == "project-a"
    assert projects[0].description == "demo"
    assert count == 0
    assert remaining == []

    await client.close()
    await resources.close()


@pytest.mark.anyio
async def test_sdk_memory_add_search_list_delete(tmp_path: Path):
    client, resources = await _build_sdk_client(tmp_path)
    await resources.orchestrator.create_project(org_id="org-a", project_id="project-a")
    await resources.orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
    )

    uids = await client.memory.add(
        session_key="session-a",
        semantic_set_id="session-a",
        episodes=[
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
    )
    search = await client.memory.search(
        query="favorite food",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="mixed",
    )
    listed = await client.memory.list(session_key="session-a")
    agent = await client.memory.agent(
        query="food",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="mixed",
    )
    await client.memory.delete_episodes(
        episode_uids=["ep-1"],
        semantic_set_id="session-a",
    )
    listed_after = await client.memory.list(session_key="session-a")

    assert uids == ["ep-1"]
    assert search.combined[0].identifier == "ep-1"
    assert listed[0].uid == "ep-1"
    assert agent.search.combined[0].identifier == "ep-1"
    assert listed_after == []

    await client.close()
    await resources.close()


@pytest.mark.anyio
async def test_sdk_response_schema_is_stable(tmp_path: Path):
    client, resources = await _build_sdk_client(tmp_path)
    await resources.orchestrator.create_project(org_id="org-a", project_id="project-a")
    await resources.orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
    )
    await client.memory.add(
        session_key="session-a",
        semantic_set_id="session-a",
        episodes=[
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
    )

    search = await client.memory.search(
        query="favorite food",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="mixed",
    )
    agent = await client.memory.agent(
        query="favorite food",
        session_key="session-a",
        session_id="session-a",
        semantic_set_id="session-a",
        mode="mixed",
    )
    listed = await client.memory.list(session_key="session-a")

    assert set(search.model_dump().keys()) == {
        "mode",
        "rewritten_query",
        "subqueries",
        "episodic_matches",
        "semantic_features",
        "combined",
        "expanded_context",
        "short_term_context",
    }
    assert set(search.episodic_matches[0].model_dump().keys()) == {
        "episode",
        "derivative_uid",
        "score",
    }
    assert set(search.combined[0].model_dump().keys()) == {
        "source",
        "content",
        "identifier",
        "score",
    }
    assert set(agent.model_dump().keys()) == {"search", "context_text"}
    assert set(listed[0].model_dump().keys()) == {
        "uid",
        "session_key",
        "session_id",
        "producer_id",
        "producer_role",
        "produced_for_id",
        "sequence_num",
        "content",
        "content_type",
        "episode_type",
        "created_at",
        "metadata_json",
        "filterable_metadata_json",
        "deleted",
    }

    await client.close()
    await resources.close()


@pytest.mark.anyio
async def test_sdk_config_roundtrip(tmp_path: Path):
    client, resources = await _build_sdk_client(tmp_path)

    set_type_id = await client.config.create_set_type(
        org_id="org-a",
        metadata_tags_sig="user",
        name="default",
    )
    configured = await client.config.configure_set(
        set_id="session-a",
        set_type_id=set_type_id,
        set_name="session config",
    )
    category_id = await client.config.add_category(
        name="profile",
        prompt="extract preferences",
        set_id="session-a",
    )
    tag_id = await client.config.add_tag(
        category_id=category_id,
        name="likes",
        description="liked items",
    )
    await client.config.disable_category(set_id="session-a", category_name="profile")
    episodic = await client.config.update_episodic_memory_config(top_k=7)
    short_term = await client.config.get_short_term_memory_config()
    long_term = await client.config.update_long_term_memory_config(semantic_enabled=False)

    assert configured.set_id == "session-a"
    assert (await client.config.list_set_types(org_id="org-a"))[0].id == set_type_id
    assert (await client.config.list_set_ids()) == ["session-a"]
    assert (await client.config.list_categories(set_id="session-a"))[0].id == category_id
    assert (await client.config.list_tags(category_id=category_id))[0].id == tag_id
    assert episodic.top_k == 7
    assert short_term.message_capacity > 0
    assert long_term.semantic_enabled is False

    await client.close()
    await resources.close()
