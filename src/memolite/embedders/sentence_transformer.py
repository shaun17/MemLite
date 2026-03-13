"""Sentence-transformers embedder provider."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from memolite.embedders.base import EmbedderProvider


@dataclass(slots=True)
class SentenceTransformerEmbedderProvider(EmbedderProvider):
    """Local semantic embedder backed by sentence-transformers."""

    model_name: str
    normalize_embeddings: bool = True
    _model: object | None = None

    @property
    def name(self) -> str:
        return "sentence_transformer"

    @property
    def dimensions(self) -> int:
        model = self._ensure_model()
        dim = getattr(model, "get_sentence_embedding_dimension", lambda: None)()
        if dim is None:
            raise RuntimeError("sentence-transformer model does not report embedding dimension")
        return int(dim)

    async def encode(self, text: str) -> list[float]:
        model = self._ensure_model()
        vector = await asyncio.to_thread(
            model.encode,
            text,
            normalize_embeddings=self.normalize_embeddings,
        )
        return [float(value) for value in vector]

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - exercised via tests with monkeypatch
                raise RuntimeError(
                    "sentence-transformers is not installed; install with `pip install memolite[embeddings]`"
                ) from exc
            self._model = SentenceTransformer(self.model_name)
        return self._model
