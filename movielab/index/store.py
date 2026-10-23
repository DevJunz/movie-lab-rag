"""Chroma 클라이언트 · 컬렉션 생성 · 조회 · 건수 (SPEC-F2002).

임베딩은 처음 필요할 때 만든다. 건수 · ID 조회는 임베딩 없이 동작한다(키 없이 `--count` 가능).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

DISTANCE = "cosine"  # A-19


class VectorStore:
    def __init__(
        self, client: Any, embeddings: Embeddings | Callable[[], Embeddings], settings: Any
    ) -> None:
        self.client = client
        self.settings = settings
        self._embeddings = embeddings
        self._collections: dict[str, Chroma] = {}

    @property
    def embeddings(self) -> Embeddings:
        if not isinstance(self._embeddings, Embeddings):
            self._embeddings = self._embeddings()
        return self._embeddings

    def collection(self, name: str) -> Chroma:
        """LangChain Chroma 래퍼. 없으면 코사인 거리로 만든다."""
        if name not in self._collections:
            self._collections[name] = Chroma(
                collection_name=name,
                embedding_function=self.embeddings,
                client=self.client,
                collection_metadata={"hnsw:space": DISTANCE},
            )
        return self._collections[name]

    def _raw(self, name: str) -> Any | None:
        try:
            return self.client.get_collection(name)
        except NotFoundError:
            return None

    def count(self, name: str) -> int:
        raw = self._raw(name)
        return raw.count() if raw is not None else 0

    def distance(self, name: str) -> str | None:
        raw = self._raw(name)
        return (raw.metadata or {}).get("hnsw:space") if raw is not None else None

    def get_by_ids(self, name: str, ids: list[str]) -> list[Document]:
        raw = self._raw(name)
        if raw is None or not ids:
            return []
        got = raw.get(ids=list(ids), include=["documents", "metadatas"])
        return [
            Document(page_content=text or "", metadata=meta or {}, id=doc_id)
            for doc_id, text, meta in zip(
                got["ids"], got["documents"], got["metadatas"], strict=True
            )
        ]

    def upsert(self, name: str, documents: list[Document], ids: list[str]) -> None:
        """같은 ID는 덮어쓴다 (재색인해도 건수가 늘지 않는다)."""
        self.collection(name).add_documents(documents, ids=ids)

    def delete_collection(self, name: str) -> None:
        if self._raw(name) is not None:
            self.client.delete_collection(name)
        self._collections.pop(name, None)
