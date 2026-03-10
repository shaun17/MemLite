"""Transaction helpers for MemLite storage operations."""

from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

T = TypeVar("T")


async def run_in_transaction(
    session_factory: async_sessionmaker[AsyncSession],
    callback: Callable[[AsyncSession], Awaitable[T]],
) -> T:
    """Run the callback in a managed transaction."""
    async with session_factory() as session:
        async with session.begin():
            return await callback(session)
