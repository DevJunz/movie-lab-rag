"""도메인 프로필 자료형. 도메인마다 다른 문구와 규칙을 담는다 (SPEC-NF2005 §3.2).

값은 `movielab/data/`의 프로필 모듈이 채운다. 다른 패키지는 이 자료형만 알고 값은 주입받는다.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

_LABEL_FIELDS = (
    "item_label",
    "expert_role",
    "assistant_role",
    "meta_source_label",
    "doc_source_label",
    "meta_link_label",
)


@dataclass(frozen=True)
class DomainProfile:
    item_label: str
    expert_role: str
    assistant_role: str
    meta_source_label: str
    doc_source_label: str
    meta_link_label: str
    attribution_notice: str
    disclaimer: str | None = None
    # 텍스트 생성 · 항목 문서 · 조건 탐색 규칙 — 해당 SPEC(F2001 · F2003 · F2004 · F2011)에서 채운다
    to_index_text: Callable[..., str] | None = None
    item_card: Callable[..., str] | None = None
    item_doc_queries: Callable[..., list[str]] | None = None
    pick_item_doc: Callable[..., Any] | None = None
    explore_filter_spec: str = ""
    explore_where: Callable[..., dict[str, Any] | None] | None = None

    def labels(self) -> dict[str, str]:
        return {name: getattr(self, name) for name in _LABEL_FIELDS}

    def render(self, template: str, **values: Any) -> str:
        """`{item_label}` 같은 자리표시자를 프로필 라벨과 `values`로 채운다.

        아는 이름만 바꾸고 나머지 중괄호(프롬프트의 JSON 예시 등)는 그대로 둔다.
        """
        mapping = {**self.labels(), **values}

        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            return str(mapping[name]) if name in mapping else match.group(0)

        return _PLACEHOLDER.sub(replace, template)
