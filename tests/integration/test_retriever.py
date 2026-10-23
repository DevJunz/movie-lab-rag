"""SPEC-F2006 근거 검색 및 병합 — 메타 고정 포함, 영화 범위 검색, Top-k, 병합 · 중복 제거."""

from __future__ import annotations

import dataclasses

import pytest

from movielab.container import build_services
from movielab.core.errors import IndexEmptyError, ItemNotIndexedError
from movielab.services.indexing import index_catalog
from tests.fakes import FakeClock, FakeEmbeddings
from tests.fakes.source import make_doc


def _doc(movie_id, page_id, title, text):
    return dataclasses.replace(
        make_doc(page_id, title, text=text), movie_id=movie_id, related_movie="영화"
    )


@pytest.fixture
def services(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    return services


def _index_wiki(services, *docs):
    indexer = services.doc_indexer()
    for doc in docs:
        indexer.index_document(doc)


def test_tc_f2006_01_meta_always_first(services):
    _index_wiki(services, _doc("157336", "1", "블랙홀", "[합성] 블랙홀은 무거운 천체다. " * 5))
    result = services.retriever().retrieve("157336", "전혀 관계없는 질문 조선 수군")
    first = result.evidences[0]
    assert first.n == 1 and first.source_kind == "meta"
    assert first.source_type == "영화 메타데이터"
    assert first.title == "인터스텔라 (2014)"
    assert first.url == "https://www.themoviedb.org/movie/157336"
    assert first.chunk_id == "157336"


def test_tc_f2006_02_only_selected_movie_chunks(services):
    _index_wiki(
        services,
        _doc("157336", "1", "블랙홀", "[합성] 블랙홀 사건의 지평선 이야기. " * 5),
        _doc("27205", "2", "블랙홀 꿈", "[합성] 블랙홀 사건의 지평선 이야기. " * 5),
    )
    result = services.retriever().retrieve("157336", "블랙홀 사건의 지평선")
    externals = [e for e in result.evidences if e.source_kind == "wiki"]
    assert externals and all(e.chunk_id.startswith("157336:") for e in externals)


def test_tc_f2006_03_external_sorted_by_similarity(services):
    _index_wiki(
        services,
        _doc("157336", "1", "웜홀", "[합성] 웜홀은 시공간의 지름길이다. " * 3),
        _doc("157336", "2", "블랙홀", "[합성] 블랙홀은 빛도 못 빠져나오는 천체이다. " * 3),
        _doc("157336", "3", "옥수수", "[합성] 옥수수 농사와 황사 이야기. " * 3),
    )
    result = services.retriever().retrieve("157336", "블랙홀은 빛도 못 빠져나오는 천체")
    externals = [e for e in result.evidences if e.source_kind == "wiki"]
    assert externals[0].title == "블랙홀"
    scores = [e.score for e in externals]
    assert scores == sorted(scores, reverse=True) and all(0 <= s <= 1 for s in scores)
    assert externals[0].license == "CC BY-SA 4.0" and externals[0].source_type == "위키백과"


def test_tc_f2006_05_top_k_from_settings(services):
    docs = [
        _doc("157336", str(i), f"문서{i}", f"[합성] 블랙홀 관련 문단 {i}번. " * 3)
        for i in range(10)
    ]
    _index_wiki(services, *docs)
    two = services.retriever(top_k=2).retrieve("157336", "블랙홀 관련 문단")
    four = services.retriever().retrieve("157336", "블랙홀 관련 문단")  # 설정 top_k = 4
    assert len(two.evidences) == 1 + 2 and len(four.evidences) == 1 + 4
    assert [e.n for e in four.evidences] == [1, 2, 3, 4, 5]


def test_tc_f2006_06_no_external_chunks(services):
    result = services.retriever().retrieve("157336", "블랙홀")
    assert len(result.evidences) == 1 and result.no_external


def test_tc_f2006_07_empty_meta_index(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    with pytest.raises(IndexEmptyError) as error:
        services.retriever().retrieve("157336", "블랙홀")
    assert error.value.code == "INDEX_EMPTY"


def test_tc_f2006_10_item_not_indexed(services):
    with pytest.raises(ItemNotIndexedError) as error:
        services.retriever().retrieve("없는영화", "블랙홀")
    assert error.value.code == "ITEM_NOT_INDEXED"


def test_tc_f2006_09_search_type_and_top_k_validated(tmp_settings, tmp_path):
    import json

    from movielab.config import SettingsError, load_settings

    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["retrieval"]["search_type"] = "mmr"
    path = tmp_path / "mmr.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)
    from movielab.rag.retriever import Retriever

    store = build_services(tmp_settings, embeddings=FakeEmbeddings()).store
    for bad in (0, True, "4"):
        with pytest.raises(ValueError):
            Retriever(store, top_k=bad)


def test_tc_f2006_11_no_external_after_dedup(services):
    from langchain_core.documents import Document

    meta_text = services.store.get_by_ids("movie_meta", ["157336"])[0].page_content
    copy = Document(
        page_content=meta_text,
        metadata={
            "movie_id": "157336",
            "page_id": "1",
            "title": "같은 본문",
            "source_kind": "wiki",
        },
        id="157336:1:0",
    )
    services.store.upsert("wiki_docs", [copy])
    result = services.retriever().retrieve("157336", "블랙홀")
    assert len(result.evidences) == 1
    assert result.no_external is True  # 중복 제거 뒤 외부 근거가 없다


def test_tc_f2006_14_top_k_filled_after_dedup(services):
    same = "[합성] 블랙홀 사건의 지평선 설명 " * 3
    docs = [_doc("157336", str(n), f"같은{n}", same) for n in range(1, 4)]
    docs += [
        _doc("157336", str(n), f"다른{n}", f"[합성] 블랙홀 관련 다른 내용 {n}번 " * 3)
        for n in range(10, 15)
    ]
    _index_wiki(services, *docs)
    result = services.retriever(top_k=4).retrieve("157336", same)
    externals = result.evidences[1:]
    assert len(externals) == 4
    assert len({" ".join(e.text.split()) for e in externals}) == 4


def test_tc_f2006_15_int_movie_id_and_score_range(services):
    _index_wiki(services, _doc("157336", "1", "블랙홀", "[합성] 블랙홀은 무거운 천체이다. " * 5))
    result = services.retriever().retrieve(157336, "블랙홀")
    assert result.evidences[0].title.startswith("인터스텔라")
    assert len(result.evidences) == 2 and 0 <= result.evidences[1].score <= 1


def test_tc_f2006_15_non_cosine_collection_has_no_score(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    services.store.client.create_collection("wiki_docs", metadata={"hnsw:space": "l2"})
    _index_wiki(services, _doc("157336", "1", "블랙홀", "[합성] 블랙홀은 무거운 천체이다. " * 5))
    result = services.retriever().retrieve("157336", "블랙홀")
    assert result.evidences[1].score is None
