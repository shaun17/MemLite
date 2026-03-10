"""Async retry helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    retries: int = 2,
    delay_seconds: float = 0.01,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
) -> T:
    """Retry an async operation for transient failures."""
    last_error: BaseException | None = None
    for attempt in range(retries + 1):
        try:
            return await operation()
        except retry_on as err:
            last_error = err
            if attempt >= retries:
                raise
            await asyncio.sleep(delay_seconds * (attempt + 1))
    assert last_error is not None
    raise last_error
