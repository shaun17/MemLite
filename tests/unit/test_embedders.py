import math
import sys
import types

import pytest

from memolite.common.config import Settings
from memolite.embedders.factory import create_embedder
from memolite.embedders.hash_embedder import HashEmbedderProvider, tokenize
from memolite.embedders.sentence_transformer import SentenceTransformerEmbedderProvider


def test_factory_returns_hash_provider_by_default():
    provider = create_embedder(Settings())

    assert isinstance(provider, HashEmbedderProvider)
    assert provider.name == "hash"
    assert provider.dimensions == 64


def test_hash_tokenize_handles_english_and_cjk():
    assert tokenize("hello world") == ["hello", "world"]
    zh_tokens = tokenize("机器学习")
    assert zh_tokens


@pytest.mark.anyio
async def test_hash_provider_returns_normalized_vector():
    provider = HashEmbedderProvider()

    vector = await provider.encode("机器学习 test")

    assert len(vector) == 64
    norm = math.sqrt(sum(v * v for v in vector))
    assert abs(norm - 1.0) < 1e-6
    assert vector == await provider.as_embedder_fn()("机器学习 test")


def test_factory_returns_sentence_transformer_provider_when_configured():
    provider = create_embedder(
        Settings(
            embedder_provider="sentence_transformer",
            embedder_model="sentence-transformers/all-MiniLM-L6-v2",
        )
    )

    assert isinstance(provider, SentenceTransformerEmbedderProvider)
    assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"


@pytest.mark.anyio
async def test_sentence_transformer_provider_uses_local_model_stub(monkeypatch):
    class FakeModel:
        def __init__(self, model_name: str):
            self.model_name = model_name

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, text: str, normalize_embeddings: bool = True):
            assert text == "hello"
            assert normalize_embeddings is True
            return [0.1, 0.2, 0.3]

    fake_module = types.SimpleNamespace(SentenceTransformer=FakeModel)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_module)

    provider = SentenceTransformerEmbedderProvider(model_name="fake-model")

    assert provider.dimensions == 3
    assert await provider.encode("hello") == [0.1, 0.2, 0.3]
