"""Embedder provider abstractions for MemoLite."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

EmbedderFn = Callable[[str], Awaitable[list[float]]]


class EmbedderProvider(ABC):
    """Abstract embedder provider contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider name for config and diagnostics."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Embedding vector dimensions produced by this provider."""

    @abstractmethod
    async def encode(self, text: str) -> list[float]:
        """Encode text into an embedding vector."""

    async def warm_up(self) -> None:
        """Pre-load model resources during startup.

        Default is no-op. Providers with heavy initialization should override
        this so startup pays the load cost instead of the first request.
        """

    def as_embedder_fn(self) -> EmbedderFn:
        """Return a function adapter matching existing EmbedderFn call sites."""
        return self.encode
