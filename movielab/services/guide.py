"""관람 가이드 (SPEC-F2010 §3.1).

고정 요청 문장으로 수집 → 그래프(task=guide) → 소제목 보장 → 인용 선별.
"""

from __future__ import annotations

from typing import Any

from movielab.core import messages
from movielab.core.errors import ItemNotFoundError
from movielab.core.types import GuideResult
from movielab.prompts import GUIDE_HEADINGS
from movielab.rag.citations import select_cited
from movielab.services.pipeline import Progress, run_graph

__all__ = ["GUIDE_HEADINGS", "GuideService"]


def ensure_headings(markdown: str) -> str:
    """빠진 고정 소제목을 '문서에서 확인되지 않습니다'와 함께 채운다 (AC-F2010-02)."""
    text = markdown.strip()
    for heading in GUIDE_HEADINGS:
        if heading not in text:
            text += f"\n\n{heading}\n{messages.GUIDE_MISSING}."
    return text


class GuideService:
    def __init__(self, catalog: Any, collector: Any, graph: Any) -> None:
        """`graph`는 Top-k를 설정 값의 2배로 만든 그래프 (container가 조립)."""
        self.catalog = catalog
        self.collector = collector
        self.graph = graph

    def generate(self, movie_id: str, on_progress: Progress | None = None) -> GuideResult:
        item = self.catalog.get(movie_id)
        if item is None:
            raise ItemNotFoundError(f"항목 없음: {movie_id}")
        request = messages.GUIDE_REQUEST.format(name=item.display_name)
        report = self.collector.collect(item, request, on_progress)
        state = run_graph(
            self.graph,
            {"movie_id": item.item_id, "question": request, "task": "guide"},
            on_progress,
        )
        markdown = ensure_headings(state["answer"])
        cited = select_cited(markdown, state["contexts"])
        return GuideResult(
            markdown=markdown,
            evidences=state["contexts"],
            cited=cited.cited,
            uncited=cited.uncited,
            collect=report,
        )
