"""문자 2-gram 해시 임베딩. 글자가 많이 겹치는 텍스트끼리 벡터가 가깝다 (결정적)."""

from __future__ import annotations

import math
import zlib

from langchain_core.embeddings import Embeddings


class FakeEmbeddings(Embeddings):
    def __init__(self, size: int = 256) -> None:
        self.size = size
        self.calls = 0

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        compact = "".join(text.split())
        grams = [compact[i : i + 2] for i in range(len(compact) - 1)] or [compact]
        for gram in grams:
            vector[zlib.crc32(gram.encode("utf-8")) % self.size] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return self._embed(text)
