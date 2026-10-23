"""SPEC-F2002 TC-15 — VectorStore 임베딩 해결: 팩토리는 한 번만 호출, 덕 타이핑 객체는 그대로."""

from __future__ import annotations

import chromadb
from chromadb.config import Settings as ChromaSettings

from movielab.index.store import VectorStore
from tests.fakes import FakeEmbeddings


class DuckEmbeddings:
    """Embeddings를 상속하지 않았지만 같은 메서드를 가진 객체."""

    def __init__(self):
        self.inner = FakeEmbeddings()

    def embed_documents(self, texts):
        return self.inner.embed_documents(texts)

    def embed_query(self, text):
        return self.inner.embed_query(text)


def _client(tmp_path):
    return chromadb.PersistentClient(
        path=str(tmp_path / "c"), settings=ChromaSettings(anonymized_telemetry=False)
    )


def test_tc_f2002_15_duck_typed_embeddings_used_directly(tmp_path, tmp_settings):
    duck = DuckEmbeddings()
    store = VectorStore(_client(tmp_path), tmp_settings, embeddings=duck)
    assert store.embeddings is duck
    store.collection("col_a")
    store.collection("col_b")
    assert store.embeddings is duck


def test_tc_f2002_15_factory_called_once(tmp_path, tmp_settings):
    calls = []

    def factory():
        calls.append(1)
        return DuckEmbeddings()

    store = VectorStore(_client(tmp_path), tmp_settings, embeddings_factory=factory)
    first = store.embeddings
    store.collection("col_a")
    store.collection("col_b")
    assert store.embeddings is first and calls == [1]
