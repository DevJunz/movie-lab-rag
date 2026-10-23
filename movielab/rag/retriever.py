"""근거 검색 및 병합 — LangGraph retrieve 노드의 본체 (SPEC-F2006).

1. 선택 항목의 메타 청크는 검색 없이 ID로 꺼내 항상 `[근거 1]`에 둔다.
2. 외부 문서 청크는 그 항목으로 범위를 좁혀(항목 ID 필터) 질문과 가까운 Top-k개를 가져온다.
3. 병합한 뒤 같은 청크 ID · 같은 본문을 한 번만 남기고 번호를 매긴다.
"""

from __future__ import annotations

import dataclasses
import hashlib
from typing import Any

from langchain_core.documents import Document

from movielab.core.errors import IndexEmptyError, ItemNotIndexedError
from movielab.core.types import ITEM_KEY, Evidence, RetrievalResult


def _text_key(text: str) -> str:
    return hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()


def merge_evidences(meta: list[Evidence], external: list[Evidence]) -> list[Evidence]:
    """메타 → 외부 순으로 합친다.

    같은 청크 ID · 같은 본문(공백 무시)은 처음 것만 남기고 1부터 번호를 매긴다.
    """
    seen_ids: set[str] = set()
    seen_texts: set[str] = set()
    merged: list[Evidence] = []
    for evidence in [*meta, *external]:
        text_key = _text_key(evidence.text)
        if evidence.chunk_id in seen_ids or text_key in seen_texts:
            continue
        seen_ids.add(evidence.chunk_id)
        seen_texts.add(text_key)
        merged.append(dataclasses.replace(evidence, n=len(merged) + 1))
    return merged


def _meta_evidence(doc: Document) -> Evidence:
    meta = doc.metadata
    year = meta.get("year")
    title = f"{meta.get('title', '')} ({year})" if year else str(meta.get("title", ""))
    return Evidence(
        n=0,
        chunk_id=str(doc.id),
        source_kind=str(meta.get("source_kind", "meta")),
        source_type=str(meta.get("source_type", "")),
        title=title,
        url=str(meta.get("url", "")),
        license=None,
        text=doc.page_content,
    )


def _external_evidence(doc: Document, distance: float) -> Evidence:
    meta: dict[str, Any] = doc.metadata
    return Evidence(
        n=0,
        chunk_id=str(doc.id),
        source_kind=str(meta.get("source_kind", "wiki")),
        source_type=str(meta.get("source_type", "")),
        title=str(meta.get("title", "")),
        url=str(meta.get("url", "")),
        license=meta.get("license"),
        text=doc.page_content,
        score=max(0.0, 1.0 - float(distance)),
        page=meta.get("page"),
    )


class Retriever:
    def __init__(self, store: Any, *, top_k: int | None = None) -> None:
        """`store`: VectorStore(F2002) — rag는 index를 import 하지 않으므로 구조로만 쓴다."""
        settings = store.settings
        self.store = store
        self.meta_collection = settings.collections.meta
        self.docs_collection = settings.collections.docs
        self.top_k = settings.retrieval.top_k if top_k is None else top_k

    def _meta(self, item_id: str) -> list[Evidence]:
        docs = self.store.get_by_ids(self.meta_collection, [item_id])
        if not docs:
            if self.store.count(self.meta_collection) == 0:
                raise IndexEmptyError("메타 색인이 비어 있다")
            raise ItemNotIndexedError(f"항목 {item_id}의 메타 청크가 없다")
        return [_meta_evidence(docs[0])]

    def _external(self, item_id: str, query: str) -> list[Evidence]:
        if self.top_k < 1 or self.store.count_where(self.docs_collection, {ITEM_KEY: item_id}) == 0:
            return []
        results = self.store.collection(self.docs_collection).similarity_search_with_score(
            query, k=self.top_k, filter={ITEM_KEY: item_id}
        )
        return [_external_evidence(doc, distance) for doc, distance in results]

    def retrieve(self, item_id: str, query: str) -> RetrievalResult:
        meta = self._meta(item_id)
        external = self._external(item_id, query)
        return RetrievalResult(evidences=merge_evidences(meta, external), no_external=not external)
