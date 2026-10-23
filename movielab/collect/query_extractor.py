"""검색어 추출 — 프롬프트 1 (SPEC-F2003).

항목 자체 문서 검색어는 LLM 결과와 상관없이 항상 앞에 둔다. LLM 출력을 읽지 못하거나
LLM 호출이 실패해도 예외를 던지지 않고 항목 자체 검색어만으로 진행한다(폴백).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from movielab.core.domain import DomainProfile
from movielab.core.jsonparse import parse_json_array
from movielab.core.text import normalize_key
from movielab.core.types import ItemRecord
from movielab.prompts import build_query_prompt

logger = logging.getLogger(__name__)


@dataclass
class QueryPlan:
    item_queries: list[str]
    llm_queries: list[str] = field(default_factory=list)
    fallback: bool = False

    @property
    def all(self) -> list[str]:
        """항목 자체 검색어 + P1 검색어 (중복 없음, 순서 유지).

        `_clean`이 이미 정리하지만, 매니페스트(NF2002)에서 되읽은 계획처럼 외부에서 만든
        `QueryPlan`도 안전하게 합치도록 여기서 한 번 더 중복을 없앤다.
        """
        seen: set[str] = set()
        merged: list[str] = []
        for query in self.item_queries + self.llm_queries:
            key = normalize_key(query)
            if key not in seen:
                seen.add(key)
                merged.append(query)
        return merged


class QueryExtractor:
    def __init__(self, llm: Any, profile: DomainProfile, settings: Any) -> None:
        self.llm = llm
        self.profile = profile
        self.settings = settings

    def _clean(self, raw: list[Any], item_queries: list[str]) -> list[str]:
        taken = {normalize_key(q) for q in item_queries}
        cleaned: list[str] = []
        for value in raw:
            if not isinstance(value, str):
                continue
            query = " ".join(value.split())
            key = normalize_key(query)
            if not query or key in taken:
                continue
            taken.add(key)
            cleaned.append(query)
        return cleaned[: int(self.settings.collect.max_queries)]

    def extract(self, item: ItemRecord, question: str) -> QueryPlan:
        profile = self.profile
        item_queries = profile.item_doc_queries(item) if profile.item_doc_queries else []
        if profile.item_card is not None:
            card = profile.item_card(item, self.settings.collect.card_overview_chars)
        else:
            card = item.display_name
        prompt = build_query_prompt(
            profile,
            item_card=card,
            question=question,
            min_queries=self.settings.collect.min_queries,
            max_queries=self.settings.collect.max_queries,
        )
        logger.debug("P1 프롬프트:\n%s", prompt)
        try:
            text = self.llm.invoke(prompt).content
        except Exception:
            logger.exception("P1 검색어 추출 LLM 호출 실패 — 항목 자체 검색어만 사용")
            return QueryPlan(item_queries=item_queries, fallback=True)
        raw = parse_json_array(text, default=[])
        llm_queries = self._clean(raw, item_queries)
        if not llm_queries:
            logger.warning("P1 출력에서 검색어를 얻지 못했다 — 항목 자체 검색어만 사용")
        return QueryPlan(item_queries, llm_queries, fallback=not llm_queries)
