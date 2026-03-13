"""Deterministic local hash embedder provider."""

from __future__ import annotations

import hashlib
import math
import re

from memolite.embedders.base import EmbedderProvider

_TOKEN_PATTERN = re.compile(r"[\w\-']+")
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
_NON_CJK_TOKEN = re.compile(r"[a-z0-9\-']+")


def tokenize(text: str) -> list[str]:
    """Tokenize text with optional CJK-aware segmentation."""
    lowered = text.lower()
    if not _CJK_PATTERN.search(lowered):
        return _TOKEN_PATTERN.findall(lowered)
    try:
        import jieba  # optional dependency
        return [t for t in jieba.cut(lowered) if t.strip()]
    except (ImportError, TypeError):
        tokens: list[str] = []
        buf = ""
        for ch in lowered:
            if _CJK_PATTERN.match(ch):
                if buf:
                    tokens.extend(_NON_CJK_TOKEN.findall(buf))
                    buf = ""
                tokens.append(ch)
            else:
                buf += ch
        if buf:
            tokens.extend(_NON_CJK_TOKEN.findall(buf))
        return tokens


class HashEmbedderProvider(EmbedderProvider):
    """Current lightweight fallback embedder wrapped as a provider."""

    def __init__(self, dimensions: int = 64) -> None:
        self._dimensions = dimensions

    @property
    def name(self) -> str:
        return "hash"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def encode(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        tokens = tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]
