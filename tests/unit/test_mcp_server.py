from pathlib import Path

import pytest
from fastmcp.exceptions import ToolError

from memlite.app.resources import ResourceManager
from memlite.common.config import Settings
from memlite.mcp.server import create_mcp_server


@pytest.mark.anyio
async def test_mcp_tools_add_search_list_get_delete_memory(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
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

    add = await server.call_tool(
        "add_memory",
        {
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
    search = await server.call_tool(
        "search_memory",
        {
            "query": "food ramen",
            "session_key": "session-a",
            "session_id": "session-a",
            "semantic_set_id": "session-a",
        },
    )
    listed = await server.call_tool("list_memory", {"session_key": "session-a"})
    fetched = await server.call_tool("get_memory", {"uid": "ep-1"})
    deleted = await server.call_tool(
        "delete_memory",
        {"episode_uids": ["ep-1"], "semantic_set_id": "session-a"},
    )
    searched_after = await server.call_tool(
        "search_memory",
        {"query": "food ramen", "session_key": "session-a", "session_id": "session-a"},
    )

    assert add.structured_content["uids"] == ["ep-1"]
    assert search.structured_content["combined"][0]["identifier"] == "ep-1"
    assert listed.structured_content["episodes"][0]["uid"] == "ep-1"
    assert fetched.structured_content["memory"]["uid"] == "ep-1"
    assert deleted.structured_content["status"] == "ok"
    assert searched_after.structured_content["combined"] == []

    await resources.close()


@pytest.mark.anyio
async def test_mcp_http_app_can_be_created(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    server = create_mcp_server(resources)

    app = server.http_app()
    tools = await server.list_tools()

    assert app is not None
    assert {tool.name for tool in tools} >= {
        "add_memory",
        "search_memory",
        "delete_memory",
    }


@pytest.mark.anyio
async def test_mcp_tool_parameter_validation(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    server = create_mcp_server(resources)

    with pytest.raises(Exception, match="Input should be a valid string"):
        await server.call_tool("add_memory", {"session_key": 123, "episodes": []})

    with pytest.raises(Exception, match="Input should be 'auto', 'episodic', 'semantic' or 'mixed'"):
        await server.call_tool("search_memory", {"query": "ramen", "mode": "bad"})

    with pytest.raises(Exception, match="greater than or equal to 1"):
        await server.call_tool("search_memory", {"query": "ramen", "limit": 0})


@pytest.mark.anyio
async def test_mcp_tool_error_path_uses_readable_message(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    server = create_mcp_server(resources)

    with pytest.raises(ToolError, match="session not found: missing-session"):
        await server.call_tool(
            "add_memory",
            {
                "session_key": "missing-session",
                "episodes": [
                    {
                        "uid": "ep-1",
                        "session_key": "missing-session",
                        "session_id": "missing-session",
                        "producer_id": "user-1",
                        "producer_role": "user",
                        "sequence_num": 1,
                        "content": "Ramen is my favorite food.",
                    }
                ],
            },
        )


@pytest.mark.anyio
async def test_mcp_tool_call_initializes_resources_on_demand(tmp_path: Path):
    resources = ResourceManager.create(
        Settings(
            sqlite_path=tmp_path / "memlite.sqlite3",
            kuzu_path=tmp_path / "graph.kuzu",
        )
    )
    assert resources._initialized is False

    server = create_mcp_server(resources)
    listed = await server.call_tool("list_memory", {"session_key": "session-a"})

    assert resources._initialized is True
    assert listed.structured_content["episodes"] == []

    await resources.close()
    assert resources._initialized is False
