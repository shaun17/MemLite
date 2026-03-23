import sys
import types

import pytest

from memolite.common.config import Settings
from memolite.episodic.search import EpisodicSearchMatch
from memolite.rerankers.cross_encoder import CrossEncoderRerankerProvider
from memolite.rerankers.factory import create_reranker
from memolite.storage.episode_store import EpisodeRecord


def _episode(uid: str, content: str) -> EpisodeRecord:
    return EpisodeRecord(
        uid=uid,
        session_key="session-key",
        session_id="session-id",
        producer_id="producer-id",
        producer_role="user",
        produced_for_id=None,
        sequence_num=int(uid[-1]) if uid[-1].isdigit() else 0,
        content=content,
        content_type="string",
        episode_type="message",
        created_at="2026-03-22T00:00:00Z",
        metadata_json=None,
        filterable_metadata_json=None,
        deleted=0,
    )


def _match(uid: str, content: str, score: float) -> EpisodicSearchMatch:
    return EpisodicSearchMatch(
        episode=_episode(uid, content),
        derivative_uid=f"drv-{uid}",
        score=score,
    )


def test_cross_encoder_provider_name():
    provider = CrossEncoderRerankerProvider(model_name="fake-model")

    assert provider.name == "cross_encoder"


@pytest.mark.anyio
async def test_cross_encoder_warm_up_loads_model(monkeypatch):
    created: list[str] = []

    class FakeCrossEncoder:
        def __init__(self, model_name: str):
            created.append(model_name)

        def predict(self, pairs):
            return [0.0 for _ in pairs]

    fake_module = types.SimpleNamespace(CrossEncoder=FakeCrossEncoder)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = CrossEncoderRerankerProvider(model_name="fake-model")

    await provider.warm_up()

    assert provider._model is not None
    assert created == ["fake-model"]


@pytest.mark.anyio
async def test_cross_encoder_rerank_sorts_by_score(monkeypatch):
    class FakeCrossEncoder:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def predict(self, pairs):
            assert pairs == [
                ("query", "doc-1"),
                ("query", "doc-2"),
                ("query", "doc-3"),
            ]
            return [0.1, 0.9, 0.5]

    fake_module = types.SimpleNamespace(CrossEncoder=FakeCrossEncoder)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = CrossEncoderRerankerProvider(model_name="fake-model")
    matches = [
        _match("ep1", "doc-1", 0.3),
        _match("ep2", "doc-2", 0.2),
        _match("ep3", "doc-3", 0.1),
    ]

    reranked = await provider.rerank("query", matches)

    assert [match.episode.uid for match in reranked] == ["ep2", "ep3", "ep1"]


@pytest.mark.anyio
async def test_cross_encoder_rerank_empty_matches():
    provider = CrossEncoderRerankerProvider(model_name="fake-model")

    assert await provider.rerank("query", []) == []


def test_factory_returns_none_when_disabled():
    assert create_reranker(Settings(reranker_provider="none")) is None


def test_factory_returns_cross_encoder_when_configured():
    provider = create_reranker(Settings(reranker_provider="cross_encoder"))

    assert isinstance(provider, CrossEncoderRerankerProvider)
    assert provider.model_name == "BAAI/bge-reranker-base"


def test_factory_respects_custom_model_name():
    provider = create_reranker(
        Settings(reranker_provider="cross_encoder", reranker_model="custom/model")
    )

    assert isinstance(provider, CrossEncoderRerankerProvider)
    assert provider.model_name == "custom/model"


def test_factory_raises_on_unknown_provider():
    with pytest.raises(ValueError, match="unsupported reranker_provider"):
        create_reranker(Settings(reranker_provider="unknown"))
