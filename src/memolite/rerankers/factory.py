"""Reranker provider factory."""

from __future__ import annotations

from memolite.common.config import Settings
from memolite.rerankers.base import RerankerProvider


def create_reranker(settings: Settings) -> RerankerProvider | None:
    """Create a reranker provider from settings. Returns None if disabled."""
    provider = getattr(settings, "reranker_provider", "none")
    if provider == "none":
        return None
    if provider == "cross_encoder":
        from memolite.rerankers.cross_encoder import CrossEncoderRerankerProvider

        model_name = settings.reranker_model or "BAAI/bge-reranker-base"
        return CrossEncoderRerankerProvider(model_name=model_name)
    raise ValueError(f"unsupported reranker_provider: {provider}")
