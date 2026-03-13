"""Tests for hash embedder tokenization and embedding behavior."""

import math
import sys
from unittest.mock import patch

import pytest

from memolite.embedders.hash_embedder import HashEmbedderProvider, tokenize


class TestEnglishTokenization:
    def test_simple_words(self):
        tokens = tokenize("machine learning")
        assert tokens == ["machine", "learning"]

    def test_lowercased(self):
        tokens = tokenize("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_punctuation_stripped(self):
        tokens = tokenize("hello, world!")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens

    def test_empty_string(self):
        assert tokenize("") == []


class TestChineseWithJieba:
    def test_word_segmentation(self):
        tokens = tokenize("机器学习")
        assert len(tokens) >= 2, f"Expected word-level tokens, got: {tokens}"
        assert "机器学习" not in tokens

    def test_different_phrases_differ(self):
        t1 = set(tokenize("机器学习"))
        t2 = set(tokenize("机器视觉"))
        assert t1 != t2

    def test_mixed_chinese_english(self):
        tokens = tokenize("机器学习 is important")
        token_set = set(tokens)
        assert "is" in token_set or any("\u4e00" <= ch <= "\u9fff" for t in tokens for ch in t)
        assert len(tokens) >= 2


class TestChineseWithoutJieba:
    def test_character_level_fallback(self):
        with patch.dict(sys.modules, {"jieba": None}):
            tokens = tokenize("机器学习")
        assert set(tokens) == {"机", "器", "学", "习"}

    def test_mixed_fallback(self):
        with patch.dict(sys.modules, {"jieba": None}):
            tokens = tokenize("深度学习 deep learning")
        assert "deep" in tokens
        assert "learning" in tokens
        cjk = [t for t in tokens if any("\u4e00" <= ch <= "\u9fff" for ch in t)]
        assert all(len(t) == 1 for t in cjk)


class TestEmbedderProperties:
    @pytest.mark.anyio
    async def test_deterministic(self):
        embedder = HashEmbedderProvider()
        v1 = await embedder.encode("机器学习")
        v2 = await embedder.encode("机器学习")
        assert v1 == v2

    @pytest.mark.anyio
    async def test_chinese_phrases_differ(self):
        embedder = HashEmbedderProvider()
        v1 = await embedder.encode("机器学习")
        v2 = await embedder.encode("自然语言处理")
        assert v1 != v2

    @pytest.mark.anyio
    async def test_l2_normalized(self):
        embedder = HashEmbedderProvider()
        vec = await embedder.encode("今天天气很好")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.anyio
    async def test_dimension_unchanged(self):
        embedder = HashEmbedderProvider()
        vec = await embedder.encode("中文测试")
        assert len(vec) == 64
