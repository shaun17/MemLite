"""Embedder provider factory."""

from __future__ import annotations

from memolite.common.config import Settings
from memolite.embedders.base import EmbedderProvider
from memolite.embedders.hash_embedder import HashEmbedderProvider
from memolite.embedders.sentence_transformer import SentenceTransformerEmbedderProvider


def create_embedder(settings: Settings) -> EmbedderProvider:
    """Create an embedder provider from settings."""
    provider = getattr(settings, "embedder_provider", "hash")
    if provider in ("hash", "default"):
        return HashEmbedderProvider()
    if provider == "sentence_transformer":
        model_name = settings.embedder_model or "BAAI/bge-small-zh-v1.5"
        return SentenceTransformerEmbedderProvider(model_name=model_name)
    raise ValueError(f"unsupported embedder_provider: {provider}")
