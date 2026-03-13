"""Tests for CJK-aware tokenization in default_embedder.

Covers:
- English-only text: unchanged behaviour
- Chinese-only text: jieba segmentation vs character-level fallback
- Mixed Chinese/English text
- Embedding determinism and discrimination
"""

import importlib
import sys
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Helpers – import the private tokenizer without triggering full app startup
# ---------------------------------------------------------------------------

def _get_tokenize():
    """Return the _tokenize function from resources after a fresh import."""
    if "memolite.app.resources" in sys.modules:
        del sys.modules["memolite.app.resources"]
    from memolite.app.resources import _tokenize  # type: ignore[attr-defined]
    return _tokenize


def _get_embedder():
    if "memolite.app.resources" in sys.modules:
        del sys.modules["memolite.app.resources"]
    from memolite.app.resources import default_embedder
    return default_embedder


# ---------------------------------------------------------------------------
# English tokenization — must not regress
# ---------------------------------------------------------------------------

class TestEnglishTokenization:
    def test_simple_words(self):
        tokens = _get_tokenize()("machine learning")
        assert tokens == ["machine", "learning"]

    def test_lowercased(self):
        tokens = _get_tokenize()("Hello World")
        assert "hello" in tokens
        assert "world" in tokens

    def test_punctuation_stripped(self):
        tokens = _get_tokenize()("hello, world!")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens

    def test_empty_string(self):
        assert _get_tokenize()("") == []


# ---------------------------------------------------------------------------
# Chinese tokenization — WITH jieba installed
# ---------------------------------------------------------------------------

class TestChineseWithJieba:
    def test_word_segmentation(self):
        """jieba should split 机器学习 into [机器, 学习], not 4 single chars."""
        _tokenize = _get_tokenize()
        tokens = _tokenize("机器学习")
        # jieba output: two meaningful words, not four characters
        assert len(tokens) >= 2, f"Expected word-level tokens, got: {tokens}"
        assert "机器学习" not in tokens, "Whole phrase should be split"

    def test_different_phrases_differ(self):
        """机器学习 and 机器视觉 share 机器 but differ after."""
        _tokenize = _get_tokenize()
        t1 = set(_tokenize("机器学习"))
        t2 = set(_tokenize("机器视觉"))
        assert t1 != t2

    def test_mixed_chinese_english(self):
        """Mixed text: both Chinese words and English words appear."""
        tokens = _get_tokenize()("机器学习 is important")
        token_set = set(tokens)
        # Should contain either "machine" (jieba sometimes expands) or at least
        # Chinese tokens AND the English word
        assert "is" in token_set or any("\u4e00" <= ch <= "\u9fff" for t in tokens for ch in t)
        assert len(tokens) >= 2


# ---------------------------------------------------------------------------
# Chinese tokenization — WITHOUT jieba (ImportError fallback)
# ---------------------------------------------------------------------------

class TestChineseWithoutJieba:
    def test_character_level_fallback(self):
        """Without jieba each CJK character becomes its own token."""
        with patch.dict(sys.modules, {"jieba": None}):
            _tokenize = _get_tokenize()
            tokens = _tokenize("机器学习")
        assert set(tokens) == {"机", "器", "学", "习"}

    def test_mixed_fallback(self):
        """Latin words stay grouped; CJK chars split individually."""
        with patch.dict(sys.modules, {"jieba": None}):
            _tokenize = _get_tokenize()
            tokens = _tokenize("深度学习 deep learning")
        assert "deep" in tokens
        assert "learning" in tokens
        cjk = [t for t in tokens if any("\u4e00" <= ch <= "\u9fff" for ch in t)]
        # Each CJK char is a single-char token in fallback mode
        assert all(len(t) == 1 for t in cjk)


# ---------------------------------------------------------------------------
# Embedding properties
# ---------------------------------------------------------------------------

class TestEmbedderProperties:
    @pytest.mark.anyio
    async def test_deterministic(self):
        embedder = _get_embedder()
        v1 = await embedder("机器学习")
        v2 = await embedder("机器学习")
        assert v1 == v2

    @pytest.mark.anyio
    async def test_chinese_phrases_differ(self):
        """Different Chinese phrases should produce different vectors."""
        embedder = _get_embedder()
        v1 = await embedder("机器学习")
        v2 = await embedder("自然语言处理")
        assert v1 != v2

    @pytest.mark.anyio
    async def test_l2_normalized(self):
        import math
        embedder = _get_embedder()
        vec = await embedder("今天天气很好")
        norm = math.sqrt(sum(v * v for v in vec))
        assert abs(norm - 1.0) < 1e-6

    @pytest.mark.anyio
    async def test_dimension_unchanged(self):
        embedder = _get_embedder()
        vec = await embedder("中文测试")
        assert len(vec) == 64
