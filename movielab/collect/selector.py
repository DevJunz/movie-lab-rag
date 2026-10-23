"""후보 선별 — 프롬프트 2 (SPEC-F2004 §3.6).

본문을 받기 전에 제목과 요약만 보여 줘서 버릴 문서를 정한다(외부 호출 절약, 명세서 2.4).
출력이 깨지거나 LLM이 실패해도 예외를 던지지 않는다 — 아무것도 고르지 않은 것으로 본다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from movielab.core.domain import DomainProfile
from movielab.core.jsonparse import parse_json_array
from movielab.core.types import Candidate, ItemRecord, Rejection
from movielab.prompts import build_selection_prompt

logger = logging.getLogger(__name__)


@dataclass
class SelectionResult:
    selected: list[Candidate] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)


def _valid_indexes(raw: list[Any], count: int) -> list[int]:
    picked: list[int] = []
    for value in raw:
        # bool은 int의 하위 타입이지만 번호가 아니다
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value < count:
            if value not in picked:
                picked.append(value)
    return picked


class CandidateSelector:
    def __init__(self, llm: Any, profile: DomainProfile, settings: Any) -> None:
        self.llm = llm
        self.profile = profile
        self.settings = settings

    def _prompt(self, item: ItemRecord, question: str, candidates: list[Candidate]) -> str:
        snippet_chars = int(self.settings.collect.snippet_chars)  # A-23
        lines = "\n".join(
            f"{i}. {c.title}: {' '.join(c.snippet.split())[:snippet_chars]}"
            for i, c in enumerate(candidates)
        )
        return build_selection_prompt(
            self.profile,
            item_name=item.display_name,
            question=question,
            candidate_lines=lines,
            max_selected=self.settings.collect.max_selected_docs,
        )

    def select(
        self, item: ItemRecord, question: str, candidates: list[Candidate]
    ) -> SelectionResult:
        if not candidates:
            return SelectionResult()
        prompt = self._prompt(item, question, candidates)
        logger.debug("P2 프롬프트:\n%s", prompt)
        try:
            text = self.llm.invoke(prompt).content
        except Exception:
            logger.exception("P2 후보 선별 LLM 호출 실패 — 선별 없음으로 처리")
            text = ""
        picked = _valid_indexes(parse_json_array(text, default=[]), len(candidates))
        limit = int(self.settings.collect.max_selected_docs)
        selected = [candidates[i] for i in picked[:limit]]
        over = {candidates[i].page_id for i in picked[limit:]}
        chosen = {c.page_id for c in selected}
        rejected = [
            Rejection(c.page_id, c.title, "over_limit" if c.page_id in over else "p2_not_selected")
            for c in candidates
            if c.page_id not in chosen
        ]
        rejected.sort(key=lambda r: r.reason == "over_limit")
        return SelectionResult(selected=selected, rejected=rejected)
