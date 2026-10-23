"""사실 여부 판정 (SPEC-F2010 §3.2): 주장으로 수집 → 그래프(task=factcheck) → 코드로 판정 후처리.

후처리는 모델 출력을 믿지 않는다: 라벨이 세 가지 밖이거나 JSON이 깨지면 `확인 불가`,
`사실` · `거짓`인데 유효한 인용이 없으면 `확인 불가`로 낮춘다(근거 없는 판정 금지).
"""

from __future__ import annotations

import logging
from typing import Any

from movielab.core import messages
from movielab.core.errors import ItemNotFoundError
from movielab.core.jsonparse import parse_json_object
from movielab.core.types import Evidence, FactCheckResult
from movielab.rag.citations import extract_citations
from movielab.services.pipeline import Progress, run_graph

logger = logging.getLogger(__name__)


def judge(answer: str, evidences: list[Evidence]) -> tuple[str, str, list[Evidence]]:
    """C1 응답 → (라벨, 이유, 인용된 근거). 번호는 검색된 근거 번호 그대로."""
    parsed = parse_json_object(answer, default=None)
    if not isinstance(parsed, dict):
        logger.warning("사실 판정 응답을 해석하지 못했다")
        return messages.VERDICT_UNKNOWN, messages.FACTCHECK_UNPARSED, []
    verdict = parsed.get("verdict")
    reason = str(parsed.get("reason") or "")
    if verdict not in messages.VERDICTS:
        verdict = messages.VERDICT_UNKNOWN
    by_number = {e.n: e for e in evidences}
    numbers = set(extract_citations(reason, count=len(evidences)))
    for value in parsed.get("citations") or []:
        if isinstance(value, int) and not isinstance(value, bool) and value in by_number:
            numbers.add(value)
    cited = [by_number[n] for n in sorted(numbers) if n in by_number]
    if verdict != messages.VERDICT_UNKNOWN and not cited:
        verdict = messages.VERDICT_UNKNOWN  # 근거 없는 판정 금지 (AC-F2010-05)
    return str(verdict), reason, cited


class FactCheckService:
    def __init__(self, catalog: Any, collector: Any, graph: Any) -> None:
        self.catalog = catalog
        self.collector = collector
        self.graph = graph

    def check(
        self, movie_id: str, claim: str, on_progress: Progress | None = None
    ) -> FactCheckResult:
        item = self.catalog.get(movie_id)
        if item is None:
            raise ItemNotFoundError(f"항목 없음: {movie_id}")
        report = self.collector.collect(item, claim, on_progress)
        state = run_graph(
            self.graph,
            {"movie_id": item.item_id, "question": claim, "task": "factcheck"},
            on_progress,
        )
        verdict, reason, cited = judge(state["answer"], state["contexts"])
        return FactCheckResult(
            claim=claim,
            verdict=verdict,
            reason=reason,
            evidences=state["contexts"],
            cited=cited,
            collect=report,
        )
