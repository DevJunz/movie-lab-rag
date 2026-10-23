"""수집 매니페스트(캐시) 인터페이스. 실제 파일 매니페스트는 SPEC-NF2002에서 더한다.

`NullManifest`는 아무것도 기억하지 않는다 — 캐시 없이도 수집 절차가 동작하게 한다(SPEC-F2004 §3.7).
"""

from __future__ import annotations


class NullManifest:
    def cached_queries(self, item_id: str, question: str) -> list[str] | None:
        return None

    def has_keyword(self, item_id: str, query: str) -> bool:
        return False

    def has_page(self, item_id: str, page_id: str) -> bool:
        return False

    def record_question(self, item_id: str, question: str, queries: list[str]) -> None:
        pass

    def record_keyword(self, item_id: str, query: str) -> None:
        pass

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> None:
        pass
