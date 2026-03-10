from pathlib import Path

import pytest

from memolite.app.resources import ResourceManager
from memolite.common.config import Settings
from memolite.mcp.server import create_mcp_server


@pytest.mark.anyio
async def test_mcp_context_and_memory_flow_integration(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memolite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
            mcp_api_key="secret-key",
        )
    )
    await resources.initialize()
    await resources.orchestrator.create_project(org_id="org-a", project_id="project-a")
    await resources.orchestrator.create_session(
        session_key="session-a",
        org_id="org-a",
        project_id="project-a",
        session_id="session-a",
        user_id="user-1",
    )
    server = create_mcp_server(resources)

    await server.call_tool(
        "set_context",
        {
            "session_key": "session-a",
            "session_id": "session-a",
            "semantic_set_id": "session-a",
            "mode": "mixed",
            "api_key": "secret-key",
        },
    )
    await server.call_tool(
        "add_memory",
        {
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
            "api_key": "secret-key",
        },
    )
    searched = await server.call_tool(
        "search_memory",
        {
            "query": "food ramen",
            "api_key": "secret-key",
        },
    )

    assert searched.structured_content["mode"] == "mixed"
    assert searched.structured_content["combined"][0]["identifier"] == "ep-1"

    await resources.close()
