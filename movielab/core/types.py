"""도메인 중립 자료형 (01-architecture.md §4.4). 도메인 고유 필드 이름은 metadata 안에만 둔다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ItemRecord:
    """항목 1건 = 색인 텍스트 1개 (F2001)."""

    item_id: str
    title: str
    year: int
    index_text: str
    metadata: dict[str, Any]
    url: str

    @property
    def display_name(self) -> str:
        return f"{self.title} ({self.year})"


@dataclass(frozen=True)
class LoadResult:
    items: list[ItemRecord] = field(default_factory=list)
    skipped: int = 0
