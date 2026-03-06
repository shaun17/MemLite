"""Async SQLite engine factory for MemLite."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from memlite.common.config import Settings
from memlite.storage.sqlite_schema import initialize_sqlite_schema


class SqliteEngineFactory:
    """Create configured async SQLite engines for MemLite."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    @property
    def sqlite_path(self) -> Path:
        return self._settings.sqlite_path

    def _build_url(self) -> str:
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{self.sqlite_path}"

    def create_engine(self) -> AsyncEngine:
        """Create or return the configured async engine."""
        if self._engine is not None:
            return self._engine

        engine = create_async_engine(self._build_url(), future=True)

        @event.listens_for(engine.sync_engine, "connect")
        def _configure_sqlite(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute("PRAGMA temp_store=MEMORY;")
            cursor.close()

        self._engine = engine
        self._session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
        return engine

    def create_session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Create or return the async session factory."""
        if self._session_factory is None:
            self.create_engine()
        assert self._session_factory is not None
        return self._session_factory

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a configured async session."""
        session_factory = self.create_session_factory()
        async with session_factory() as session:
            yield session

    async def initialize_schema(self) -> None:
        """Initialize the bootstrap SQLite schema."""
        await initialize_sqlite_schema(self.create_engine())

    async def healthcheck(self) -> bool:
        """Check SQLite connectivity."""
        engine = self.create_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar_one() == 1

    async def dispose(self) -> None:
        """Dispose the engine if it exists."""
        if self._engine is not None:
            await self._engine.dispose()
