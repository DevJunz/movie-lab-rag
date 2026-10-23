"""SPEC-F2002 영화 메타데이터 색인 (RAG 1) — 임시 Chroma + 가짜 임베딩."""

from __future__ import annotations

import dataclasses

import pytest

from movielab.container import build_services
from movielab.core.types import LoadResult
from movielab.index.meta_indexer import index_items
from movielab.services.catalog import Catalog
from movielab.services.indexing import index_catalog
from tests.fakes import FakeClock, FakeEmbeddings


@pytest.fixture
def services(tmp_settings):
    return build_services(tmp_settings, embeddings=FakeEmbeddings())


def _index(services, **kwargs):
    return index_catalog(services.catalog, services.store, sleep=FakeClock().sleep, **kwargs)


def test_tc_f2002_01_index_count_matches_loaded(services):
    report = _index(services)
    assert services.store.count("movie_meta") == 12
    assert (report.loaded, report.skipped, report.indexed, report.removed) == (12, 0, 12, 0)
    assert report.ok and report.failed_batches == []


def test_tc_f2002_02_reindex_does_not_duplicate(services):
    _index(services)
    report = _index(services)
    assert services.store.count("movie_meta") == 12
    assert report.indexed == 12 and report.ok


def test_tc_f2002_03_changed_item_overwritten_in_place(services):
    _index(services)
    items = services.catalog.items()
    changed = dataclasses.replace(items[0], index_text=items[0].index_text + "\n[수정됨]")
    index_items(
        services.store, [changed], collection="movie_meta", batch_size=100, retries=0,
        retry_wait_sec=0,
    )  # fmt: skip
    assert services.store.count("movie_meta") == 12
    doc = services.store.get_by_ids("movie_meta", [changed.item_id])[0]
    assert doc.page_content.endswith("[수정됨]")


def test_tc_f2002_04_get_by_id_returns_document_with_metadata(services):
    _index(services)
    docs = services.store.get_by_ids("movie_meta", ["157336"])
    assert len(docs) == 1
    doc = docs[0]
    assert doc.id == "157336"
    assert doc.page_content.startswith("제목: 인터스텔라 (2014)")
    meta = doc.metadata
    assert meta["source_kind"] == "meta" and meta["source_type"] == "영화 메타데이터"
    assert meta["url"] == "https://www.themoviedb.org/movie/157336"
    assert meta["year"] == 2014 and meta["original_language"] == "en"
    assert isinstance(meta["genres"], str) and "SF" in meta["genres"]
    assert services.store.get_by_ids("movie_meta", ["없는ID"]) == []


def test_tc_f2002_06_failed_batch_reported_others_kept_with_wait(tmp_settings):
    emb = FakeEmbeddings(fail_when=lambda texts: any("인셉션" in t for t in texts))
    services = build_services(tmp_settings, embeddings=emb)
    clock = FakeClock()
    report = index_catalog(services.catalog, services.store, batch_size=5, sleep=clock.sleep)
    # 12편을 5건씩: 배치 0(인터스텔라 · 인셉션 …)만 실패
    assert report.failed_batches == [0]
    assert services.store.count("movie_meta") == 7
    assert clock.sleeps == [2.0]  # 재시도 1회 전 2초 대기 (A-21)
    assert not report.ok and report.removed == 0


def test_tc_f2002_09_collection_uses_cosine(services):
    _index(services)
    assert services.store.distance("movie_meta") == "cosine"


def test_tc_f2002_10_count_and_get_without_api_key(tmp_settings):
    services = build_services(tmp_settings)  # 키 없음, 임베딩 미주입
    assert services.store.count("movie_meta") == 0
    assert services.store.get_by_ids("movie_meta", ["157336"]) == []
    assert services.store.ids("movie_meta") == []


def test_tc_f2002_13_items_removed_from_data_are_deleted(services):
    _index(services)
    remaining = [i for i in services.catalog.items() if i.item_id != "670"]
    shrunk = Catalog(lambda: LoadResult(items=remaining, skipped=0))
    report = index_catalog(shrunk, services.store, sleep=FakeClock().sleep)
    assert services.store.count("movie_meta") == 11
    assert "670" not in services.store.ids("movie_meta")
    assert (report.indexed, report.removed) == (11, 1) and report.ok
