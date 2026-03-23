"""Cross-encoder reranker backed by sentence-transformers CrossEncoder."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from memolite.episodic.search import EpisodicSearchMatch
from memolite.rerankers.base import RerankerProvider


@dataclass(slots=True)
class CrossEncoderRerankerProvider(RerankerProvider):
    """Local cross-encoder reranker."""

    model_name: str
    _model: object | None = field(default=None, repr=False)

    @property
    def name(self) -> str:
        return "cross_encoder"

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:  # pragma: no cover - exercised via tests with monkeypatch
                raise RuntimeError(
                    "sentence-transformers is not installed; install with `pip install memolite[embeddings]`"
                ) from exc
            self._model = CrossEncoder(self.model_name)
        return self._model

    async def warm_up(self) -> None:
        """Pre-load the cross-encoder model into memory."""
        await asyncio.to_thread(self._ensure_model)

    async def rerank(
        self, query: str, matches: list[EpisodicSearchMatch]
    ) -> list[EpisodicSearchMatch]:
        if not matches:
            return matches

        model = self._ensure_model()
        pairs = [(query, match.episode.content) for match in matches]
        scores = await asyncio.to_thread(model.predict, pairs)
        scored = sorted(
            zip(scores, matches),
            key=lambda item: float(item[0]),
            reverse=True,
        )
        return [match for _, match in scored]
