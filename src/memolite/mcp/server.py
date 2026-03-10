"""MCP server integration for MemLite."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Annotated, Literal, TypeVar

from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field
from sqlalchemy.exc import IntegrityError

from memolite.api.schemas import dump_episode_payload
from memolite.api.schemas import EpisodeInput
from memolite.app.resources import ResourceManager
from memolite.common.config import Settings, get_settings

T = TypeVar("T")
CONTEXT_STATE_KEY = "memlite_runtime_context"


@dataclass(slots=True)
class McpRuntimeContext:
    """Session-scoped defaults shared across MCP tool calls."""

    session_key: str | None = None
    session_id: str | None = None
    semantic_set_id: str | None = None
    mode: Literal["auto", "episodic", "semantic", "mixed"] | None = None
    limit: int | None = None
    context_window: int | None = None


def create_mcp_server(resources: ResourceManager | None = None) -> FastMCP:
    """Create an MCP server bound to the MemLite resource graph."""
    settings = get_settings() if resources is None else resources.settings
    runtime = resources or ResourceManager.create(settings)
    mcp = FastMCP(
        name="MemLite MCP",
        instructions="MemLite memory tools for episodic and semantic retrieval.",
        version="0.1.0",
    )
    local_context = McpRuntimeContext()

    async def ensure_initialized() -> None:
        await runtime.initialize()

    async def authorize(api_key: str | None) -> None:
        expected = runtime.settings.mcp_api_key
        if expected is None:
            return
        if api_key != expected:
            raise ToolError("unauthorized")

    async def require_session(session_key: str) -> None:
        session = await runtime.session_store.get_session(session_key)
        if session is None:
            raise ToolError(f"session not found: {session_key}")

    async def get_runtime_context(ctx: Context) -> McpRuntimeContext:
        nonlocal local_context
        if ctx.request_context is None and getattr(ctx, "_session", None) is None:
            return local_context
        stored = await ctx.get_state(CONTEXT_STATE_KEY)
        if not isinstance(stored, dict):
            return McpRuntimeContext()
        return McpRuntimeContext(**stored)

    async def save_runtime_context(
        ctx: Context,
        *,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] | None = None,
        limit: int | None = None,
        context_window: int | None = None,
    ) -> McpRuntimeContext:
        nonlocal local_context
        current = await get_runtime_context(ctx)
        merged = McpRuntimeContext(
            session_key=session_key if session_key is not None else current.session_key,
            session_id=session_id if session_id is not None else current.session_id,
            semantic_set_id=(
                semantic_set_id
                if semantic_set_id is not None
                else current.semantic_set_id
            ),
            mode=mode if mode is not None else current.mode,
            limit=limit if limit is not None else current.limit,
            context_window=(
                context_window
                if context_window is not None
                else current.context_window
            ),
        )
        if ctx.request_context is None and getattr(ctx, "_session", None) is None:
            local_context = merged
            return merged
        await ctx.set_state(CONTEXT_STATE_KEY, asdict(merged))
        return merged

    @mcp.tool(
        name="set_context",
        description="Set session-scoped defaults for subsequent MemLite MCP calls.",
    )
    async def set_context(
        ctx: Context,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] | None = None,
        limit: Annotated[int | None, Field(ge=1, le=100)] = None,
        context_window: Annotated[int | None, Field(ge=0, le=20)] = None,
        api_key: str | None = None,
    ) -> dict[str, object]:
        await ensure_initialized()
        await authorize(api_key)
        context = await save_runtime_context(
            ctx,
            session_key=session_key,
            session_id=session_id,
            semantic_set_id=semantic_set_id,
            mode=mode,
            limit=limit,
            context_window=context_window,
        )
        return {"context": asdict(context)}

    @mcp.tool(
        name="get_context",
        description="Read the current session-scoped MemLite MCP defaults.",
    )
    async def get_context(ctx: Context, api_key: str | None = None) -> dict[str, object]:
        await ensure_initialized()
        await authorize(api_key)
        return {"context": asdict(await get_runtime_context(ctx))}

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
        ctx: Context,
        episodes: Sequence[dict],
        session_key: str | None = None,
        semantic_set_id: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, object]:
        await ensure_initialized()
        await authorize(api_key)
        context = await save_runtime_context(
            ctx,
            session_key=session_key,
            semantic_set_id=semantic_set_id,
        )
        if context.session_key is None:
            raise ToolError("session_key is required")
        await require_session(context.session_key)

        async def run() -> list:
            return await runtime.orchestrator.add_episodes(
                session_key=context.session_key,
                semantic_set_id=context.semantic_set_id,
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
        ctx: Context,
        query: str,
        session_key: str | None = None,
        session_id: str | None = None,
        semantic_set_id: str | None = None,
        mode: Literal["auto", "episodic", "semantic", "mixed"] | None = None,
        limit: Annotated[int | None, Field(ge=1, le=100)] = None,
        context_window: Annotated[int | None, Field(ge=0, le=20)] = None,
        api_key: str | None = None,
    ) -> dict[str, object]:
        await ensure_initialized()
        await authorize(api_key)
        stored = await get_runtime_context(ctx)
        resolved_mode = mode if mode is not None else (stored.mode or "auto")
        resolved_limit = limit if limit is not None else (stored.limit or 5)
        resolved_context_window = (
            context_window
            if context_window is not None
            else (stored.context_window or 1)
        )
        resolved_session_key = session_key if session_key is not None else stored.session_key
        resolved_session_id = session_id if session_id is not None else stored.session_id
        resolved_semantic_set_id = (
            semantic_set_id
            if semantic_set_id is not None
            else stored.semantic_set_id
        )
        await save_runtime_context(
            ctx,
            session_key=resolved_session_key,
            session_id=resolved_session_id,
            semantic_set_id=resolved_semantic_set_id,
            mode=resolved_mode,
            limit=resolved_limit,
            context_window=resolved_context_window,
        )
        result = await call_tool(
            "search_memory",
            lambda: runtime.orchestrator.search_memories(
                query=query,
                session_key=resolved_session_key,
                session_id=resolved_session_id,
                semantic_set_id=resolved_semantic_set_id,
                mode=resolved_mode,
                limit=resolved_limit,
                context_window=resolved_context_window,
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
        ctx: Context,
        episode_uids: Sequence[str],
        semantic_set_id: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, str]:
        await ensure_initialized()
        await authorize(api_key)
        stored = await get_runtime_context(ctx)
        resolved_semantic_set_id = (
            semantic_set_id
            if semantic_set_id is not None
            else stored.semantic_set_id
        )
        await call_tool(
            "delete_memory",
            lambda: runtime.orchestrator.delete_episodes(
                episode_uids=list(episode_uids),
                semantic_set_id=resolved_semantic_set_id,
            ),
        )
        return {"status": "ok"}

    @mcp.tool(
        name="list_memory",
        description="List episodic memory for a session key.",
    )
    async def list_memory(
        ctx: Context,
        session_key: str | None = None,
        api_key: str | None = None,
    ) -> dict[str, object]:
        await ensure_initialized()
        await authorize(api_key)
        stored = await get_runtime_context(ctx)
        resolved_session_key = session_key if session_key is not None else stored.session_key
        if resolved_session_key is None:
            raise ToolError("session_key is required")
        episodes = await call_tool(
            "list_memory",
            lambda: runtime.episode_store.list_episodes(session_key=resolved_session_key),
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
    async def get_memory(
        uid: str,
        api_key: str | None = None,
    ) -> dict[str, object | None]:
        await ensure_initialized()
        await authorize(api_key)
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
