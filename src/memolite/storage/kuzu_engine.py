"""Kùzu bootstrap and query helpers for MemLite."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any

import kuzu

from memolite.common.config import Settings
from memolite.common.retry import retry_async

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
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="memolite-kuzu")
        self._connection_lock = asyncio.Lock()

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

    async def _run_in_executor(self, fn, /, *args):  # type: ignore[no-untyped-def]
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, lambda: fn(*args))

    async def create_database(self) -> kuzu.Database:
        """Create or return the active Kùzu database."""
        if self._database is None:
            await self.initialize_data_dir()
            self._database = await self._run_in_executor(
                kuzu.Database,
                str(self.database_path),
            )
        return self._database

    async def create_connection(self) -> kuzu.Connection:
        """Create or return the active Kùzu connection."""
        if self._connection is None:
            database = await self.create_database()
            self._connection = await self._run_in_executor(kuzu.Connection, database)
        return self._connection

    async def initialize_schema(self) -> None:
        """Create base graph schema required by episodic memory."""
        async with self._connection_lock:
            connection = await self.create_connection()
            for statement in KUZU_BOOTSTRAP_STATEMENTS:
                await self._run_in_executor(connection.execute, statement)

    async def execute(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Execute a mutating Kùzu query."""
        async with self._connection_lock:
            connection = await self.create_connection()
            await retry_async(
                lambda: self._run_in_executor(connection.execute, query, parameters)
            )

    async def query(
        self,
        query: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[list[object]]:
        """Run a read query and return all rows."""
        started = perf_counter()
        async with self._connection_lock:
            connection = await self.create_connection()
            result = await retry_async(
                lambda: self._run_in_executor(connection.execute, query, parameters)
            )
            rows: list[list[object]] = []
            while result.has_next():
                rows.append(await self._run_in_executor(result.get_next))
        if self._metrics is not None:
            self._metrics.increment("graph_queries_total")
            self._metrics.observe_timing(
                "graph_query_latency_ms",
                (perf_counter() - started) * 1000,
            )
        return rows

    async def close(self) -> None:
        """Release in-process Kùzu handles."""
        async with self._connection_lock:
            if self._connection is not None:
                await self._run_in_executor(self._connection.close)
                self._connection = None
            if self._database is not None:
                await self._run_in_executor(self._database.close)
                self._database = None
        self._executor.shutdown(wait=True)
