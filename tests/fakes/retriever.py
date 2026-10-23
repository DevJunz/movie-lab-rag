"""가짜 검색기 — 정해 둔 근거를 돌려주고 호출을 남긴다 (그래프 테스트용)."""

from __future__ import annotations

from movielab.core.types import Evidence, RetrievalResult


class FakeRetriever:
    def __init__(self, evidences: list[Evidence]) -> None:
        self.evidences = evidences
        self.calls: list[tuple[str, str]] = []

    def retrieve(self, item_id: str, query: str) -> RetrievalResult:
        self.calls.append((item_id, query))
        no_external = all(e.source_kind == "meta" for e in self.evidences)
        return RetrievalResult(evidences=self.evidences, no_external=no_external)
