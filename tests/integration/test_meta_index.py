"""SPEC-F2002 영화 메타데이터 색인 (RAG 1) — 임시 Chroma + 가짜 임베딩."""

from __future__ import annotations

import dataclasses

import pytest

from movielab.container import build_services
from movielab.services.indexing import index_catalog
from tests.fakes import FakeEmbeddings


class FailingEmbeddings(FakeEmbeddings):
    """`fail_on`번째(1부터) embed_documents 호출과 그 재시도를 모두 실패시킨다."""

    def __init__(self, fail_batches: set[int], batch_size: int) -> None:
        super().__init__()
        self.fail_batches = fail_batches
        self.batch_size = batch_size

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        first = texts[0]
        if any(f"[실패대상{b}]" in first for b in self.fail_batches):
            raise RuntimeError("임베딩 서버 오류")
        return super().embed_documents(texts)


@pytest.fixture
def services(tmp_settings):
    return build_services(tmp_settings, embeddings=FakeEmbeddings())


def test_tc_f2002_01_index_count_matches_loaded(services):
    report = index_catalog(services.catalog, services.store, services.settings)
    assert services.store.count("movie_meta") == 12
    assert (report.loaded, report.skipped, report.indexed) == (12, 0, 12)
    assert report.ok and report.failed_batches == []


def test_tc_f2002_02_reindex_does_not_duplicate(services):
    index_catalog(services.catalog, services.store, services.settings)
    report = index_catalog(services.catalog, services.store, services.settings)
    assert services.store.count("movie_meta") == 12
    assert report.indexed == 12 and report.ok


def test_tc_f2002_03_changed_item_overwritten_in_place(services):
    index_catalog(services.catalog, services.store, services.settings)
    items = services.catalog.items()
    changed = dataclasses.replace(items[0], index_text=items[0].index_text + "\n[수정됨]")
    from movielab.index.meta_indexer import index_items

    index_items(services.store, [changed], collection="movie_meta")
    assert services.store.count("movie_meta") == 12
    doc = services.store.get_by_ids("movie_meta", [changed.item_id])[0]
    assert doc.page_content.endswith("[수정됨]")


def test_tc_f2002_04_get_by_id_returns_document_with_metadata(services):
    index_catalog(services.catalog, services.store, services.settings)
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


def test_tc_f2002_04_collection_uses_cosine(services):
    index_catalog(services.catalog, services.store, services.settings)
    assert services.store.distance("movie_meta") == "cosine"


def test_tc_f2002_06_failed_batch_reported_and_others_kept(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    items = services.catalog.items()
    marked = [
        dataclasses.replace(item, index_text=f"[실패대상1]{item.index_text}") if i == 5 else item
        for i, item in enumerate(items)
    ]
    from movielab.index.meta_indexer import index_items

    emb = FailingEmbeddings({1}, batch_size=5)
    services = build_services(tmp_settings, embeddings=emb)
    failed = index_items(services.store, marked, collection="movie_meta", batch_size=5)
    assert failed == [1]
    assert services.store.count("movie_meta") == 7  # 배치 0(5건) + 배치 2(2건)


def test_tc_f2002_05_count_works_without_api_key(tmp_settings):
    services = build_services(tmp_settings)  # 키 없음, 임베딩 미주입
    assert services.store.count("movie_meta") == 0
    assert services.store.get_by_ids("movie_meta", ["157336"]) == []
