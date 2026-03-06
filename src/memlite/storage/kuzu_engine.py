"""Kùzu bootstrap and query helpers for MemLite."""

from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter

import kuzu

from memlite.common.config import Settings
from memlite.common.retry import retry_async

KUZU_BOOTSTRAP_STATEMENTS = (
    """
    CREATE NODE TABLE IF NOT EXISTS Episode(
        uid STRING,
        session_id STRING,
        content STRING,
        content_type STRING,
        created_at STRING,
        metadata_json STRING,
        PRIMARY KEY(uid)
    )
    """,
    """
    CREATE NODE TABLE IF NOT EXISTS Derivative(
        uid STRING,
        episode_uid STRING,
        session_id STRING,
        content STRING,
        content_type STRING,
        sequence_num INT64,
        metadata_json STRING,
        PRIMARY KEY(uid)
    )
    """,
    """
    CREATE REL TABLE IF NOT EXISTS DERIVED_FROM(
        FROM Derivative TO Episode,
        relation_type STRING
    )
    """,
)


class KuzuEngineFactory:
    """Manage Kùzu database directory, connection and schema lifecycle."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._database: kuzu.Database | None = None
        self._connection: kuzu.Connection | None = None
        self._metrics = None

    def bind_metrics(self, metrics) -> None:  # type: ignore[no-untyped-def]
        self._metrics = metrics

    @property
    def database_path(self) -> Path:
        """Return the configured Kùzu database path."""
        return self._settings.kuzu_path

    async def initialize_data_dir(self) -> Path:
        """Ensure the parent directory for the Kùzu database exists."""
        path = self.database_path.parent
        path.mkdir(parents=True, exist_ok=True)
        return path

    async def create_database(self) -> kuzu.Database:
        """Create or return the active Kùzu database."""
        if self._database is None:
            await self.initialize_data_dir()
            self._database = await asyncio.to_thread(
                kuzu.Database,
                str(self.database_path),
            )
        return self._database

    async def create_connection(self) -> kuzu.Connection:
        """Create or return the active Kùzu connection."""
        if self._connection is None:
            database = await self.create_database()
            self._connection = await asyncio.to_thread(kuzu.Connection, database)
        return self._connection

    async def initialize_schema(self) -> None:
        """Create base graph schema required by episodic memory."""
        connection = await self.create_connection()
        for statement in KUZU_BOOTSTRAP_STATEMENTS:
            await asyncio.to_thread(connection.execute, statement)

    async def execute(self, query: str) -> None:
        """Execute a mutating Kùzu query."""
        connection = await self.create_connection()
        await retry_async(lambda: asyncio.to_thread(connection.execute, query))

    async def query(self, query: str) -> list[list[object]]:
        """Run a read query and return all rows."""
        started = perf_counter()
        connection = await self.create_connection()
        result = await retry_async(lambda: asyncio.to_thread(connection.execute, query))
        rows: list[list[object]] = []
        while result.has_next():
            rows.append(await asyncio.to_thread(result.get_next))
        if self._metrics is not None:
            self._metrics.increment("graph_queries_total")
            self._metrics.observe_timing(
                "graph_query_latency_ms",
                (perf_counter() - started) * 1000,
            )
        return rows

    async def close(self) -> None:
        """Release in-process Kùzu handles."""
        self._connection = None
        self._database = None
