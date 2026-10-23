"""RAG 없는 직접 답변 — RAG 전후 비교의 기준선 (SPEC-F2015 §2.2)."""

from __future__ import annotations

from typing import Any

from movielab.core.domain import DomainProfile
from movielab.prompts import build_direct_prompt
from movielab.services.catalog import Catalog


class DirectAnswerService:
    """같은 LLM에 근거 없이 항목 이름과 질문만 준다."""

    def __init__(self, catalog: Catalog, llm: Any, profile: DomainProfile) -> None:
        self._catalog = catalog
        self._llm = llm
        self._profile = profile

    def ask(self, item_id: str, question: str) -> str | None:
        """답변 문자열. 카탈로그에 없는 항목이면 None."""
        item = self._catalog.get(item_id)
        if item is None:
            return None
        prompt = build_direct_prompt(self._profile, item_name=item.display_name, question=question)
        return str(self._llm.invoke(prompt).content)
