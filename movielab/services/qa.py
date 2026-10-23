"""질문 하나를 처리한다: 수집 → retrieve · generate 그래프 → 인용 선별.

(SPEC-F2009 §3.3, 01-architecture §3.2) 수집은 그래프 밖에서 한다 — 그래프는 명세서대로
노드 두 개(F2007)이고, 수집 단계는 진행 상태(F2012)로 보여야 하기 때문이다.
이전 대화는 넣지 않는다(A-08, 단일 턴).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from movielab.core.errors import ItemNotFoundError
from movielab.core.types import AnswerResult
from movielab.rag.citations import select_cited
from movielab.rag.graph import is_not_found

Progress = Callable[[str, dict[str, Any]], None]


class QAService:
    def __init__(
        self,
        catalog: Any,
        collector: Any,
        graph: Any,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """의존 객체가 제공해야 하는 것.

        `catalog.get(id)`, `collector.collect(item, question, on_progress)`,
        `graph.invoke(state)`.
        """
        self.catalog = catalog
        self.collector = collector
        self.graph = graph
        self.clock = clock

    def ask(
        self, movie_id: str, question: str, on_progress: Progress | None = None
    ) -> AnswerResult:
        started = self.clock()
        item = self.catalog.get(movie_id)
        if item is None:
            raise ItemNotFoundError(f"항목 없음: {movie_id}")
        report = self.collector.collect(item, question, on_progress)
        collected = self.clock()
        state = self.graph.invoke({"movie_id": item.item_id, "question": question, "task": "qa"})
        answer, evidences = state["answer"], state["contexts"]
        cited = select_cited(answer, evidences)
        return AnswerResult(
            answer=answer,
            evidences=evidences,
            cited=cited.cited,
            uncited=cited.uncited,
            not_found=is_not_found(answer),
            collect=report,
            notices=list(report.notices),
            timings={"collect": collected - started, "total": self.clock() - started},
        )
