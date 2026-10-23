"""SPEC-F2001 TC-09 — Catalog는 주입받은 로더로 영화 목록을 한 번만 읽는다."""

from __future__ import annotations

from movielab.core.types import ItemRecord, LoadResult
from movielab.services.catalog import Catalog


def _record(item_id: str) -> ItemRecord:
    return ItemRecord(
        item_id=item_id, title=f"제목{item_id}", year=2000, index_text="t", metadata={}, url=""
    )


def test_tc_f2001_09_catalog_loads_once_and_gets_by_id():
    calls = []

    def loader() -> LoadResult:
        calls.append(1)
        return LoadResult(items=[_record("1"), _record("2")], skipped=3)

    catalog = Catalog(loader)
    assert [i.item_id for i in catalog.items()] == ["1", "2"]
    assert catalog.items() is catalog.items()
    assert catalog.get("2").title == "제목2"
    assert catalog.get("9") is None
    assert catalog.skipped == 3
    assert calls == [1]


def test_tc_f2001_09_container_wires_movie_loader(tmp_settings):
    from movielab.container import build_services

    catalog = build_services(tmp_settings).catalog
    assert len(catalog.items()) == 12
    assert catalog.get("157336").title == "인터스텔라"
