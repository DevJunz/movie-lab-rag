"""PDF 청킹 · 색인 (SPEC-F2016 §2.2).

위키와 다르게 **쪽 안에서만** 자른다(근거에 쪽 번호를 정확히 표시하려고). 청크 ID는
`{movie_id}:pdf:{doc_id}:{쪽}:{순번}` — 매니페스트의 영화마다 청크를 따로 만들어 `movie_id`
필터 규칙을 지킨다. 새 청크를 먼저 쓰고 이번 분할에 없는 옛 청크만 지운다(위키 색인과 같은 규칙).
"""

from __future__ import annotations

from typing import Any, Protocol

import openai
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from movielab.config import chunking_ok
from movielab.core.errors import InvalidApiKeyError
from movielab.core.messages import PDF_SOURCE_LABEL
from movielab.core.types import ITEM_KEY
from movielab.index.store import VectorStore


class PdfEntryLike(Protocol):
    doc_id: str
    file: str
    title: str
    source_url: str
    license: str
    item_ids: tuple[str, ...]


class PdfPageLike(Protocol):
    number: int
    text: str


class PdfIndexer:
    def __init__(self, store: VectorStore) -> None:
        chunking = store.settings.chunking
        self.store = store
        self.collection = store.settings.collections.pdf
        self.chunk_size = chunking.pdf_chunk_size
        self.chunk_overlap = chunking.pdf_chunk_overlap
        if not chunking_ok(self.chunk_size, self.chunk_overlap):
            raise ValueError(
                f"잘못된 PDF 청크 값: size={self.chunk_size}, overlap={self.chunk_overlap}"
            )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap
        )

    def _metadata(self, entry: PdfEntryLike, item_id: str, page: int, index: int) -> dict:
        return {
            ITEM_KEY: item_id,
            "doc_id": entry.doc_id,
            "file": entry.file,
            "page": page,
            "title": entry.title,
            "url": entry.source_url,
            "license": entry.license,
            "chunk_index": index,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "source_kind": "pdf",
            "source_type": PDF_SOURCE_LABEL,
        }

    def _where(self, item_id: str, doc_id: str) -> dict[str, Any]:
        return {"$and": [{ITEM_KEY: item_id}, {"doc_id": doc_id}]}

    def index_pdf(self, entry: PdfEntryLike, pages: list[PdfPageLike]) -> int:
        """PDF 1건을 영화마다 색인한다. 반환: 색인한 청크 수 (모든 영화 합)."""
        documents: list[Document] = []
        for item_id in entry.item_ids:
            for page in pages:
                chunks = [c for c in self.splitter.split_text(page.text) if c.strip()]
                for index, chunk in enumerate(chunks):
                    documents.append(
                        Document(
                            page_content=chunk,
                            metadata=self._metadata(entry, str(item_id), page.number, index),
                            id=f"{item_id}:pdf:{entry.doc_id}:{page.number}:{index}",
                        )
                    )
        size = self.store.settings.indexing.batch_size
        try:
            for start in range(0, len(documents), size):
                self.store.upsert(self.collection, documents[start : start + size])
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise InvalidApiKeyError(str(exc)) from exc
        new_ids = {doc.id for doc in documents}
        stale = [
            chunk_id
            for item_id in entry.item_ids
            for chunk_id in self.store.ids_where(
                self.collection, self._where(str(item_id), entry.doc_id)
            )
            if chunk_id not in new_ids
        ]
        for start in range(0, len(stale), size):
            self.store.delete_ids(self.collection, stale[start : start + size])
        return len(documents)
