"""기록 호출을 남기는 가짜 매니페스트 (캐시 기록 시점 검사용)."""

from __future__ import annotations

from movielab.collect.manifest import NullManifest


class RecordingManifest(NullManifest):
    def __init__(self) -> None:
        self.keywords: list[str] = []
        self.pages: list[tuple[str, int]] = []
        self.questions: list[str] = []

    def record_keyword(self, item_id: str, query: str) -> None:
        self.keywords.append(query)

    def record_page(self, item_id, page_id, title, chunks, *, rejected=False) -> None:
        self.pages.append((str(page_id), chunks))

    def record_question(self, item_id, question, queries) -> None:
        self.questions.append(question)
