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


@dataclass(frozen=True)
class IndexReport:
    """메타 색인 결과 (F2002).

    `loaded`는 로드한 원소 수(항목 + 건너뜀), `indexed`는 로드한 ID 중 색인된 수.
    """

    loaded: int
    skipped: int
    indexed: int
    failed_batches: list[int] = field(default_factory=list)
    removed: int = 0  # 데이터에서 빠져 지운 고아 문서 수

    @property
    def ok(self) -> bool:
        return self.loaded - self.skipped == self.indexed and not self.failed_batches
