"""근거 검색 및 병합 — LangGraph retrieve 노드의 본체 (SPEC-F2006).

1. 선택 항목의 메타 청크는 검색 없이 ID로 꺼내 항상 `[근거 1]`에 둔다.
2. 외부 문서 청크는 그 항목으로 범위를 좁혀(항목 ID 필터) 질문과 가까운 Top-k개를 가져온다.
3. 병합한 뒤 같은 청크 ID · 같은 본문을 한 번만 남기고 번호를 매긴다.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable
from typing import Any

from langchain_core.documents import Document

from movielab.core.errors import IndexEmptyError, ItemNotIndexedError
from movielab.core.types import ITEM_KEY, Evidence, RetrievalResult
from movielab.rag.pdf_search import add_pdf_evidences, search_pdf


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


def default_meta_title(metadata: dict[str, Any]) -> str:
    """프로필이 제목 형식을 주지 않을 때 — 메타데이터의 `title` 그대로."""
    return str(metadata.get("title", ""))


def _meta_evidence(doc: Document, meta_title: Callable[[dict[str, Any]], str]) -> Evidence:
    meta = doc.metadata
    title = meta_title(meta)
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


def _external_evidence(doc: Document, distance: float | None) -> Evidence:
    """`distance`가 None이면(코사인이 아닌 컬렉션) 점수를 비운다."""
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
        score=None if distance is None else min(1.0, max(0.0, 1.0 - float(distance))),
        page=meta.get("page"),
    )


class Retriever:
    def __init__(
        self,
        store: Any,
        *,
        top_k: int | None = None,
        meta_title: Callable[[dict[str, Any]], str] | None = None,
        search_type: str | None = None,
        pdf_top_k: int | None = None,
    ) -> None:
        """`store`: VectorStore(F2002) — rag는 index를 import 하지 않으므로 구조로만 쓴다.

        `meta_title`은 DomainProfile의 메타 근거 제목 형식 (없으면 메타데이터 `title`).
        """
        settings = store.settings
        self.store = store
        self.meta_collection = settings.collections.meta
        self.docs_collection = settings.collections.docs
        self.top_k = settings.retrieval.top_k if top_k is None else top_k
        if isinstance(self.top_k, bool) or not isinstance(self.top_k, int) or self.top_k < 1:
            raise ValueError(f"top_k는 1 이상이어야 한다: {self.top_k!r}")
        self.meta_title = meta_title or default_meta_title
        retrieval = settings.retrieval
        self.search_type = retrieval.search_type if search_type is None else search_type
        if self.search_type not in ("similarity", "mmr"):
            raise ValueError(f"search_type은 similarity 또는 mmr이어야 한다: {self.search_type!r}")
        self.fetch_k = retrieval.mmr_fetch_k
        self.lambda_mult = retrieval.mmr_lambda
        # PDF 근거 (F2016): 0이면 PDF를 검색하지 않는다
        self.pdf_collection = settings.collections.pdf
        self.pdf_top_k = settings.retrieval.pdf_top_k if pdf_top_k is None else pdf_top_k

    def _meta(self, item_id: str) -> list[Evidence]:
        docs = self.store.get_by_ids(self.meta_collection, [item_id])
        if not docs:
            if self.store.count(self.meta_collection) == 0:
                raise IndexEmptyError("메타 색인이 비어 있다")
            raise ItemNotIndexedError(f"항목 {item_id}의 메타 청크가 없다")
        return [_meta_evidence(docs[0], self.meta_title)]

    def _merged(self, item_id: str, query: str, meta: list[Evidence]) -> list[Evidence]:
        """메타 + 외부 Top-k를 병합한다. 중복 제거로 `top_k`보다 적어지면 더 가져온다."""
        where = {ITEM_KEY: item_id}
        if not self.store.has_where(self.docs_collection, where):
            return merge_evidences(meta, [])
        cosine = self.store.distance(self.docs_collection) == "cosine"
        collection = self.store.collection(self.docs_collection)
        k = self.top_k
        while True:
            results = self._search(collection, query, k, where)
            externals = [_external_evidence(doc, d if cosine else None) for doc, d in results]
            merged = merge_evidences(meta, externals)
            if len(merged) - len(meta) >= self.top_k or len(results) < k:
                return merged[: len(meta) + self.top_k]
            k *= 2

    def _search(
        self, collection: Any, query: str, k: int, where: dict[str, str]
    ) -> list[tuple[Document, float | None]]:
        """(문서, 거리) 목록. MMR이면 다양성으로 고르고 거리는 유사도 검색 결과에서 찾는다."""
        if self.search_type != "mmr":
            return collection.similarity_search_with_score(query, k=k, filter=where)
        fetch_k = max(self.fetch_k, k)
        docs = collection.max_marginal_relevance_search(
            query, k=k, fetch_k=fetch_k, lambda_mult=self.lambda_mult, filter=where
        )
        scored = collection.similarity_search_with_score(query, k=fetch_k, filter=where)
        distances = {str(doc.id): d for doc, d in scored}
        return [(doc, distances.get(str(doc.id))) for doc in docs]

    def check(self, item_id: str) -> None:
        """메타 색인에 이 항목이 있는지만 확인한다 (없으면 안내 오류) — 수집 전 점검용."""
        self._meta(str(item_id))

    def retrieve(self, item_id: str, query: str) -> RetrievalResult:
        item_id = str(item_id)
        meta = self._meta(item_id)
        evidences = self._merged(item_id, query, meta)
        pdf = search_pdf(self.store, self.pdf_collection, item_id, query, self.pdf_top_k)
        evidences = add_pdf_evidences(evidences, len(meta), pdf, merge_evidences)
        # 중복 제거 뒤 남은 외부 근거로 판단한다 (메타와 같은 본문뿐이면 '없음')
        return RetrievalResult(evidences=evidences, no_external=len(evidences) == len(meta))
