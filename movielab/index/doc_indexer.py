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
from movielab.core.types import SourceDocument
from movielab.index.store import VectorStore

ITEM_KEY = "movie_id"  # 청크 메타데이터의 항목 ID 키 (검색 필터 · 청크 ID에 쓴다)


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

    def delete_document(self, item_id: str, page_id: str) -> int:
        return self.store.delete_where(self.collection, self._where(item_id, page_id))

    def indexed_pages(self, item_id: str | None = None) -> set[tuple[str, str]]:
        """색인된 `(항목 ID, 문서 ID)` 쌍. `item_id`를 주면 그 항목 범위만."""
        where = {ITEM_KEY: str(item_id)} if item_id is not None else None
        return {
            (str(meta.get(ITEM_KEY)), str(meta.get("page_id")))
            for meta in self.store.metadatas(self.collection, where)
        }

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
            self.store.upsert(self.collection, documents)  # 실패하면 옛 청크는 그대로 남는다
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
        self.store.delete_ids(self.collection, stale)
        return len(documents)
