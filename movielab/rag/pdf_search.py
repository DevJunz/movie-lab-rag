"""PDF 근거 검색과 위키 근거와의 결합 (SPEC-F2016 §2.3).

`Retriever`가 위키 병합을 마친 뒤 `add_pdf_evidences`를 한 번 부른다. 같은 임베딩 · 코사인 거리라
위키와 PDF 점수를 비교할 수 있으므로 외부 근거를 점수 순으로 섞은 뒤 중복 제거 · 번호를 다시 매긴다.
PDF 컬렉션이 없거나 그 항목의 청크가 없으면 입력을 그대로 돌려준다(MVP와 같음).
"""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from movielab.core.types import ITEM_KEY, Evidence


def _pdf_evidence(doc: Document, distance: float | None) -> Evidence:
    meta: dict[str, Any] = doc.metadata
    page = meta.get("page")
    return Evidence(
        n=0,
        chunk_id=str(doc.id),
        source_kind=str(meta.get("source_kind", "pdf")),
        source_type=str(meta.get("source_type", "")),
        title=str(meta.get("title", "")),
        url=str(meta.get("url", "")),
        license=meta.get("license"),
        text=doc.page_content,
        score=None if distance is None else min(1.0, max(0.0, 1.0 - float(distance))),
        page=None if page is None else int(page),
        file=meta.get("file"),
    )


def search_pdf(store: Any, collection: str, item_id: str, query: str, k: int) -> list[Evidence]:
    """그 항목의 PDF 청크 중 질문과 가까운 `k`개 (없으면 빈 목록)."""
    where = {ITEM_KEY: str(item_id)}
    if k < 1 or not store.has_where(collection, where):
        return []
    cosine = store.distance(collection) == "cosine"
    results = store.collection(collection).similarity_search_with_score(query, k=k, filter=where)
    return [_pdf_evidence(doc, d if cosine else None) for doc, d in results]


def add_pdf_evidences(
    merged: list[Evidence], meta_count: int, pdf: list[Evidence], merge: Any
) -> list[Evidence]:
    """`merged`(메타 + 위키, 번호 매김 끝)에 PDF 근거를 점수 순으로 섞는다.

    `merge`는 retriever의 `merge_evidences`(중복 제거 · 번호 부여)다. 점수가 없는 근거는 뒤로.
    """
    if not pdf:
        return merged
    meta, externals = merged[:meta_count], [*merged[meta_count:], *pdf]
    externals.sort(key=lambda e: -1.0 if e.score is None else e.score, reverse=True)
    return merge(meta, externals)
