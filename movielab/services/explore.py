"""조건 기반 항목 탐색 (SPEC-F2011): 조건 해석(E1) → 구조 필터 + 의미 검색 → 조건 선별(E2) → 검증.

도메인 필드 이름(연도 · 언어 …)은 `DomainProfile.explore_where`가 Chroma `where`로 바꾼다.
여기서는 그 `where`를 해석해 결과를 다시 검사할 뿐 필드 이름을 모른다(NF2005).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from movielab.core.jsonparse import parse_json_array, parse_json_object
from movielab.core.types import ITEM_KEY, ExploreItem, ExploreResult
from movielab.prompts import build_explore_parse_prompt, build_explore_select_prompt

logger = logging.getLogger(__name__)

Progress = Callable[[str, dict[str, Any]], None]

_COMPARE: dict[str, Callable[[Any, Any], bool]] = {
    "$eq": lambda value, target: value == target,
    "$gte": lambda value, target: value >= target,
    "$lte": lambda value, target: value <= target,
}


def matches_where(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
    """Chroma `where`(`$and` · `$eq` · `$gte` · `$lte`, 값만 주면 `$eq`)를 메타데이터에 적용한다."""
    if not where:
        return True
    for key, condition in where.items():
        if key == "$and":
            if not all(matches_where(metadata, part) for part in condition):
                return False
            continue
        if key not in metadata:
            return False
        checks = condition if isinstance(condition, dict) else {"$eq": condition}
        for operator, target in checks.items():
            compare = _COMPARE.get(operator)
            try:
                if compare is None or not compare(metadata[key], target):
                    return False
            except TypeError:
                return False
    return True


class ExploreService:
    def __init__(self, catalog: Any, store: Any, llm: Any, profile: Any, settings: Any) -> None:
        """의존 객체가 제공해야 하는 것.

        `catalog.get(id)`, `store.collection(이름).similarity_search(...)`, `llm.invoke(prompt)`.
        """
        self.catalog = catalog
        self.store = store
        self.llm = llm
        self.profile = profile
        self.settings = settings

    def _parse(self, condition: str) -> dict[str, Any]:
        """E1. 깨지면 조건 원문으로 의미 검색만 한다."""
        raw = self.llm.invoke(build_explore_parse_prompt(self.profile, condition)).content
        parsed = parse_json_object(raw, default=None)
        if not isinstance(parsed, dict) or not isinstance(parsed.get("semantic_query"), str):
            logger.warning("조건 해석 응답을 읽지 못해 원문으로 검색한다")
            return {"semantic_query": condition}
        return parsed

    def _candidates(self, query: str, where: dict[str, Any] | None) -> list[Any]:
        collection = self.store.collection(self.settings.collections.meta)
        k = self.settings.explore.candidates
        docs = (
            collection.similarity_search(query, k=k, filter=where)
            if where
            else (collection.similarity_search(query, k=k))
        )
        items = [self.catalog.get(str(doc.metadata.get(ITEM_KEY, doc.id))) for doc in docs]
        return [item for item in items if item is not None]

    def _select(self, condition: str, candidates: list[Any]) -> list[tuple[str, str]]:
        """E2. 깨지면 아무것도 고르지 않는다."""
        chars = self.settings.collect.card_overview_chars
        card = self.profile.item_card or (lambda item, _: item.display_name)
        # 순번을 붙이지 않는다 — 모델이 순번을 id로 돌려주지 않게 (SPEC-F2011 §3.1-4)
        lines = "\n".join(f"- id={item.item_id} | {card(item, chars)}" for item in candidates)
        raw = self.llm.invoke(build_explore_select_prompt(self.profile, condition, lines)).content
        picked = parse_json_array(raw, default=[]) or []
        result = []
        for entry in picked:
            if isinstance(entry, dict) and entry.get(ITEM_KEY) is not None:
                result.append((str(entry[ITEM_KEY]), str(entry.get("reason") or "")))
        return result

    def search(self, condition: str, on_progress: Progress | None = None) -> ExploreResult:
        def progress(stage: str) -> None:
            if on_progress is not None:
                on_progress(stage, {})

        progress("explore_parse")
        parsed = self._parse(condition)
        where = self.profile.explore_where(parsed) if self.profile.explore_where else None
        progress("explore_search")
        candidates = self._candidates(parsed["semantic_query"], where)
        progress("explore_select")
        picked = self._select(condition, candidates) if candidates else []

        by_id = {item.item_id: item for item in candidates}
        items: list[ExploreItem] = []
        for item_id, reason in picked:
            item = by_id.get(item_id)  # 후보 밖(지어낸) 결과는 버린다
            if item is None or any(e.item.item_id == item_id for e in items):
                continue
            if not matches_where(item.metadata, where):  # 구조 조건은 코드로 다시 확인
                continue
            items.append(ExploreItem(item, reason))
            if len(items) >= self.settings.explore.max_results:
                break
        return ExploreResult(
            condition=condition, parsed=parsed, candidates=len(candidates), items=items
        )
