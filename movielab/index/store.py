"""Chroma 클라이언트 · 컬렉션 생성 · 조회 · 건수 (SPEC-F2002).

임베딩은 처음 필요할 때 만든다. 건수 · ID 조회는 임베딩 없이 동작한다(키 없이 `--count` 가능).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from chromadb.errors import NotFoundError
from langchain_chroma import Chroma
from langchain_core.documents import Document

DISTANCE = "cosine"  # A-19


class VectorStore:
    def __init__(
        self,
        client: Any,
        settings: Any,
        *,
        embeddings: Any = None,
        embeddings_factory: Callable[[], Any] | None = None,
    ) -> None:
        """임베딩 객체 또는 팩토리 중 하나를 받는다. 팩토리는 처음 필요할 때 한 번만 부른다."""
        self.client = client
        self.settings = settings
        self._embeddings = embeddings
        self._factory = embeddings_factory
        self._collections: dict[str, Chroma] = {}

    @property
    def embeddings(self) -> Any:
        if self._embeddings is None:
            if self._factory is None:
                raise ValueError("VectorStore에 임베딩이 없다")
            self._embeddings = self._factory()
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

    def ids(self, name: str) -> list[str]:
        raw = self._raw(name)
        return list(raw.get(include=[])["ids"]) if raw is not None else []

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

    def upsert(self, name: str, documents: list[Document]) -> None:
        """ID는 `Document.id`. 같은 ID는 덮어쓴다 (재색인해도 건수가 늘지 않는다)."""
        self.collection(name).add_documents(documents, ids=[doc.id for doc in documents])

    def delete_ids(self, name: str, ids: list[str]) -> None:
        raw = self._raw(name)
        if raw is not None and ids:
            raw.delete(ids=list(ids))

    def delete_collection(self, name: str) -> None:
        if self._raw(name) is not None:
            self.client.delete_collection(name)
        self._collections.pop(name, None)
