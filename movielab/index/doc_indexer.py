"""외부 문서 청킹 · 색인 (RAG 2, SPEC-F2005).

청크 크기 · 중복은 설정에서만 읽는다. 청크 ID는 `{movie_id}:{page_id}:{순번}` — 여러 영화가 같은
문서를 수집해도 덮어쓰지 않는다. 같은 문서를 다시 색인할 때는 새 청크를 먼저 쓰고, 이번 분할에
없는 옛 청크만 지운다 — 청크 수가 줄어도 옛 청크가 남지 않고,
쓰기(임베딩)가 실패하면 옛 색인이 남는다.
"""

from __future__ import annotations

from typing import Any

import openai
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from movielab.config import chunking_ok
from movielab.core.errors import InvalidApiKeyError
from movielab.core.types import ITEM_KEY, SourceDocument
from movielab.index.store import VectorStore


class DocIndexer:
    def __init__(
        self,
        store: VectorStore,
        *,
        source_type: str,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        """`source_type`은 DomainProfile의 외부 문서 라벨 (container가 넘긴다).

        청크 값을 주지 않으면 설정 파일 값을 쓴다 (재색인 스크립트의 일시 덮어쓰기용 인자).
        """
        chunking = store.settings.chunking
        self.store = store
        self.collection = store.settings.collections.docs
        self.source_type = source_type
        self.chunk_size = chunking.chunk_size if chunk_size is None else chunk_size
        self.chunk_overlap = chunking.chunk_overlap if chunk_overlap is None else chunk_overlap
        if not chunking_ok(self.chunk_size, self.chunk_overlap):
            raise ValueError(
                f"잘못된 청크 값: size={self.chunk_size}, overlap={self.chunk_overlap}"
            )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )

    def _metadata(self, doc: SourceDocument, index: int) -> dict[str, Any]:
        return {
            ITEM_KEY: str(doc.movie_id),
            "page_id": str(doc.page_id),
            "title": doc.title,
            "url": doc.url,
            "related_movie": doc.related_movie,
            "search_query": doc.search_query,
            "collected_at": doc.collected_at,
            "is_item_doc": bool(doc.is_item_doc),
            "chunk_index": index,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "source_kind": doc.source_kind,
            "source_type": self.source_type,
            "license": doc.license,
        }

    def _where(self, item_id: str, page_id: str) -> dict[str, Any]:
        return {"$and": [{ITEM_KEY: str(item_id)}, {"page_id": str(page_id)}]}

    def _delete_ids(self, ids: list[str]) -> None:
        """`indexing.batch_size`개씩 나눠 지운다 (Chroma 한 번 호출 한도)."""
        size = self.store.settings.indexing.batch_size
        for start in range(0, len(ids), size):
            self.store.delete_ids(self.collection, ids[start : start + size])

    def delete_document(self, item_id: str, page_id: str) -> int:
        return self.store.delete_where(self.collection, self._where(item_id, page_id))

    def _pages(self, item_id: str | None) -> list[tuple[str, tuple[str, str]]]:
        where = {ITEM_KEY: str(item_id)} if item_id is not None else None
        return [
            (chunk_id, (str(meta.get(ITEM_KEY)), str(meta.get("page_id"))))
            for chunk_id, meta in self.store.entries(self.collection, where)
        ]

    def page_ids(self, item_id: str) -> set[str]:
        """그 항목의 색인에 청크가 있는 문서 ID (수집 캐시 대조용, NF2002)."""
        return {page_id for _, (_, page_id) in self._pages(item_id)}

    def has_pages(self, item_id: str | None = None) -> bool:
        """색인된 청크가 하나라도 있는지 (한 건만 읽는다)."""
        if item_id is None:
            return self.store.count(self.collection) > 0
        return self.store.has_where(self.collection, {ITEM_KEY: str(item_id)})

    def prune(self, keep: set[tuple[str, str]], item_id: str | None = None) -> set[tuple[str, str]]:
        """`keep`에 없는 문서의 청크를 한 번에 지운다. 반환: 지운 `(항목 ID, 문서 ID)` 쌍."""
        stale = [(chunk_id, page) for chunk_id, page in self._pages(item_id) if page not in keep]
        self._delete_ids([chunk_id for chunk_id, _ in stale])
        return {page for _, page in stale}

    def index_document(self, doc: SourceDocument) -> int:
        """문서 1건을 청킹해 색인한다. 반환: 색인한 청크 수.

        본문이 비면 `ValueError`(옛 청크는 그대로), 임베딩 인증 오류는 `InvalidApiKeyError`.
        """
        chunks = [c for c in self.splitter.split_text(doc.text) if c.strip()]
        if not chunks:
            raise ValueError(f"본문이 비어 있다: {doc.movie_id}/{doc.page_id}")
        documents = [
            Document(
                page_content=chunk,
                metadata=self._metadata(doc, index),
                id=f"{doc.movie_id}:{doc.page_id}:{index}",
            )
            for index, chunk in enumerate(chunks)
        ]
        try:
            size = self.store.settings.indexing.batch_size  # Chroma 한 번 호출 한도를 넘지 않게
            for start in range(0, len(documents), size):
                # 실패하면 옛 청크는 그대로 남는다
                self.store.upsert(self.collection, documents[start : start + size])
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise InvalidApiKeyError(str(exc)) from exc
        new_ids = {d.id for d in documents}
        stale = [
            chunk_id
            for chunk_id in self.store.ids_where(
                self.collection, self._where(doc.movie_id, doc.page_id)
            )
            if chunk_id not in new_ids
        ]
        self._delete_ids(stale)
        return len(documents)
