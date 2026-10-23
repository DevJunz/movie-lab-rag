"""항목 목록 조회. 로더는 조립 지점이 주입한다 (services는 data를 직접 import 하지 않는다)."""

from __future__ import annotations

from collections.abc import Callable

from movielab.core.types import ItemRecord, LoadResult


class Catalog:
    def __init__(self, loader: Callable[[], LoadResult]) -> None:
        self._loader = loader
        self._result: LoadResult | None = None
        self._by_id: dict[str, ItemRecord] = {}

    def _load(self) -> LoadResult:
        if self._result is None:
            self._result = self._loader()
            self._by_id = {item.item_id: item for item in self._result.items}
        return self._result

    def items(self) -> list[ItemRecord]:
        return self._load().items

    def get(self, item_id: str) -> ItemRecord | None:
        self._load()
        return self._by_id.get(str(item_id))

    @property
    def skipped(self) -> int:
        return self._load().skipped
