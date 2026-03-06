"""MCP server integration for MemLite."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Literal, TypeVar

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from sqlalchemy.exc import IntegrityError

from memlite.api.schemas import dump_episode_payload
from memlite.api.schemas import EpisodeInput
from memlite.app.resources import ResourceManager
from memlite.common.config import Settings, get_settings

T = TypeVar("T")


def create_mcp_server(resources: ResourceManager | None = None) -> FastMCP:
    """Create an MCP server bound to the MemLite resource graph."""
    settings = get_settings() if resources is None else resources.settings
    runtime = resources or ResourceManager.create(settings)
    mcp = FastMCP(
        name="MemLite MCP",
        instructions="MemLite memory tools for episodic and semantic retrieval.",
        version="0.1.0",
    )

    async def ensure_initialized() -> None:
        await runtime.initialize()

    async def require_session(session_key: str) -> None:
        session = await runtime.session_store.get_session(session_key)
        if session is None:
            raise ToolError(f"session not found: {session_key}")

    async def call_tool(operation: str, callback: Callable[[], Awaitable[T]]) -> T:
        try:
            return await callback()
        except ToolError:
            raise
        except IntegrityError as err:
            raise ToolError(f"{operation} failed: integrity constraint violated") from err
        except ValueError as err:
            raise ToolError(f"{operation} failed: {err}") from err
        except Exception as err:
            raise ToolError(f"{operation} failed") from err

    @mcp.tool(
        name="add_memory",
        description="Add episodic memories into a session and optional semantic set.",
    )
    async def add_memory(
        session_key: str,
        episodes: Sequence[dict],
        semantic_set_id: str | None = None,
    ) -> dict[str, object]:
        await ensure_initialized()
        await require_session(session_key)

        async def run() -> list:
            return await runtime.orchestrator.add_episodes(
                session_key=session_key,
                semantic_set_id=semantic_set_id,
                episodes=[
                    dump_episode_payload(EpisodeInput.model_validate(item))
                    for item in episodes
                ],
            )

        persisted = await call_tool("add_memory", run)
        return {"uids": [episode.uid for episode in persisted]}

    @mcp.tool(
        name="search_memory",
        description="Search episodic, semantic or mixed memory for a query.",
    )
    async def search_memory(
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] = "auto",
        limit: Annotated[int, Field(ge=1, le=100)] = 5,
    ) -> dict[str, object]:
        await ensure_initialized()
        result = await call_tool(
            "search_memory",
            lambda: runtime.orchestrator.search_memories(
                query=query,
                session_key=session_key,
                session_id=session_id,
                semantic_set_id=semantic_set_id,
                mode=mode,
                limit=limit,
            ),
        )
        return {
            "mode": result.mode,
            "combined": [
                {
                    "source": item.source,
                    "content": item.content,
                    "identifier": item.identifier,
                    "score": item.score,
                }
                for item in result.combined
            ],
            "short_term_context": result.short_term_context,
        }

    @mcp.tool(
        name="delete_memory",
        description="Delete episodic memories and optionally clean semantic references.",
    )
    async def delete_memory(
        episode_uids: Sequence[str],
        semantic_set_id: str | None = None,
    ) -> dict[str, str]:
        await ensure_initialized()
        await call_tool(
            "delete_memory",
            lambda: runtime.orchestrator.delete_episodes(
                episode_uids=list(episode_uids),
                semantic_set_id=semantic_set_id,
            ),
        )
        return {"status": "ok"}

    @mcp.tool(
        name="list_memory",
        description="List episodic memory for a session key.",
    )
    async def list_memory(session_key: str) -> dict[str, object]:
        await ensure_initialized()
        episodes = await call_tool(
            "list_memory",
            lambda: runtime.episode_store.list_episodes(session_key=session_key),
        )
        return {
            "episodes": [
                {
                    "uid": episode.uid,
                    "session_key": episode.session_key,
                    "session_id": episode.session_id,
                    "producer_id": episode.producer_id,
                    "producer_role": episode.producer_role,
                    "sequence_num": episode.sequence_num,
                    "content": episode.content,
                    "content_type": episode.content_type,
                    "episode_type": episode.episode_type,
                    "created_at": episode.created_at,
                }
                for episode in episodes
            ]
        }

    @mcp.tool(
        name="get_memory",
        description="Get a single episodic memory item by uid.",
    )
    async def get_memory(uid: str) -> dict[str, object | None]:
        await ensure_initialized()
        episodes = await call_tool(
            "get_memory",
            lambda: runtime.episode_store.get_episodes([uid]),
        )
        if not episodes:
            return {"memory": None}
        episode = episodes[0]
        return {
            "memory": {
                "uid": episode.uid,
                "session_key": episode.session_key,
                "session_id": episode.session_id,
                "producer_id": episode.producer_id,
                "producer_role": episode.producer_role,
                "sequence_num": episode.sequence_num,
                "content": episode.content,
                "content_type": episode.content_type,
                "episode_type": episode.episode_type,
                "created_at": episode.created_at,
            }
        }

    return mcp


async def run_stdio(settings: Settings | None = None) -> None:
    """Run the MemLite MCP server over stdio."""
    runtime = ResourceManager.create(settings or get_settings())
    server = create_mcp_server(runtime)
    try:
        await server.run_stdio_async(show_banner=False)
    finally:
        await runtime.close()


async def run_http(settings: Settings | None = None) -> None:
    """Run the MemLite MCP server over HTTP."""
    runtime = ResourceManager.create(settings or get_settings())
    server = create_mcp_server(runtime)
    try:
        await server.run_http_async(
            show_banner=False,
            host=runtime.settings.host,
            port=runtime.settings.port,
            path="/mcp",
        )
    finally:
        await runtime.close()
