"""SPEC-F2014 MMR 검색 — 다양성, 메타 고정, 영화 범위."""

from __future__ import annotations

import dataclasses
import json

import pytest

from movielab.config import load_settings
from movielab.container import build_services
from movielab.services.indexing import index_catalog
from tests.fakes import FakeClock, FakeEmbeddings
from tests.fakes.source import make_doc

DUP = "[합성] 블랙홀은 빛조차 빠져나오지 못하는 무거운 천체이다 사건의 지평선"


def _doc(movie_id, page_id, title, text):
    return dataclasses.replace(
        make_doc(page_id, title, text=text), movie_id=movie_id, related_movie="영화"
    )


def index_mmr_fixture(services):
    """거의 같은 청크 3개 + 다른 주제 3개 + 다른 영화 1개 (합성)."""
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    indexer = services.doc_indexer()
    docs = [
        _doc("157336", "1", "중복A", f"{DUP} 가."),
        _doc("157336", "2", "중복B", f"{DUP} 나."),
        _doc("157336", "3", "중복C", f"{DUP} 다."),
        _doc("157336", "4", "웜홀", "[합성] 블랙홀 근처 웜홀은 시공간을 잇는 통로라고 한다."),
        _doc("157336", "5", "옥수수", "[합성] 블랙홀 영화 속 옥수수 농사와 황사 이야기."),
        _doc("157336", "6", "음악", "[합성] 블랙홀 장면의 오르간 음악은 작곡가가 만들었다."),
        _doc("27205", "7", "다른영화", f"{DUP} 라."),
    ]
    for doc in docs:
        indexer.index_document(doc)


@pytest.fixture
def services(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    index_mmr_fixture(services)
    return services


def _externals(result):
    return [e for e in result.evidences if e.source_kind != "meta"]


def test_tc_f2014_01_mmr_diversifies(services):
    sim_result = services.retriever(top_k=3, search_type="similarity").retrieve("157336", DUP)
    mmr_result = services.retriever(top_k=3, search_type="mmr").retrieve("157336", DUP)
    sim, mmr = _externals(sim_result), _externals(mmr_result)
    assert len(sim) == 3 and len(mmr) == 3
    assert sum(e.title.startswith("중복") for e in sim) >= 2
    assert sum(e.title.startswith("중복") for e in mmr) <= 1
    assert len({e.title for e in mmr}) > len({e.title for e in sim}) or len(
        {e.title for e in sim}
    ) == len(sim)
    assert all(e.score is not None and 0 <= e.score <= 1 for e in mmr)


def test_tc_f2014_01_mmr_from_settings(tmp_settings, tmp_path):
    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["retrieval"]["search_type"] = "mmr"
    path = tmp_path / "mmr.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    services = build_services(load_settings(path), embeddings=FakeEmbeddings())
    retriever = services.retriever()
    assert retriever.search_type == "mmr"
    assert retriever.fetch_k == raw["retrieval"]["mmr_fetch_k"]
    assert retriever.lambda_mult == raw["retrieval"]["mmr_lambda"]
    # 기본 설정은 유사도 (MVP 동작 유지)
    assert build_services(tmp_settings, embeddings=FakeEmbeddings()).retriever().search_type == (
        "similarity"
    )


def test_tc_f2014_02_mmr_meta_first_and_scoped(services):
    result = services.retriever(search_type="mmr").retrieve("157336", DUP)
    assert result.evidences[0].n == 1 and result.evidences[0].source_kind == "meta"
    assert [e.n for e in result.evidences] == list(range(1, len(result.evidences) + 1))
    externals = _externals(result)
    assert externals and all(e.chunk_id.startswith("157336:") for e in externals)
    assert not result.no_external
