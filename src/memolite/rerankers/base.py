"""Reranker provider abstractions for MemoLite."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from memolite.episodic.search import EpisodicSearchMatch

RerankerFn = Callable[[str, list[EpisodicSearchMatch]], Awaitable[list[EpisodicSearchMatch]]]


class RerankerProvider(ABC):
    """Abstract reranker provider contract."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable provider name for config and diagnostics."""

    @abstractmethod
    async def rerank(
        self, query: str, matches: list[EpisodicSearchMatch]
    ) -> list[EpisodicSearchMatch]:
        """Rerank matches by relevance to query. Return reordered list."""

    async def warm_up(self) -> None:
        """Pre-load model resources during startup. Default is no-op."""

    def as_reranker_fn(self) -> RerankerFn:
        """Return a function adapter matching existing RerankerFn call sites."""
        return self.rerank
