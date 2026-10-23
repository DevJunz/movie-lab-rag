"""SPEC-NF2002 수집 캐시 — 같은 질문 · 겹치는 검색어 · 같은 문서는 다시 수집하지 않는다."""

from __future__ import annotations

import pytest

from movielab.collect.collector import Collector
from movielab.collect.manifest import Manifest
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.core.errors import ExternalSourceUnavailableError
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from tests.fakes import FakeChatModel, pick_titles
from tests.fakes.source import FakeSource, make_doc

ITEM_INTRO = "[합성] 인터스텔라는 2014년 개봉한 크리스토퍼 놀란 감독의 SF 영화이다."


@pytest.fixture
def item(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _source():
    source = FakeSource()
    source.add(make_doc("1", "인터스텔라"), title_intro=ITEM_INTRO)
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    source.add(make_doc("4", "웜홀"), queries=["웜홀", "블랙홀"])
    source.add(make_doc("5", "중력"), queries=["중력"])
    return source


class Setup:
    def __init__(self, tmp_settings, *, chunk_counter=None, mode="auto"):
        tmp_settings.raw["collect"]["source"] = mode
        self.source = _source()
        self.indexed: list[str] = []
        self.p1 = {"질문1": '["블랙홀"]', "질문2": '["블랙홀", "중력"]'}
        self.llm = FakeChatModel(
            rules={
                "검색어 추출": lambda prompt: self.p1["질문2" if "질문2" in prompt else "질문1"],
                "후보 선별": pick_titles("블랙홀", "웜홀", "중력"),
            }
        )
        self.manifest = Manifest(tmp_settings.path("manifest"))
        self.collector = Collector(
            api_source=self.source,
            bundle_source=FakeSource("bundle"),
            extractor=QueryExtractor(self.llm, MOVIE_PROFILE, tmp_settings),
            selector=CandidateSelector(self.llm, MOVIE_PROFILE, tmp_settings),
            raw_store=RawStore(tmp_settings.path("raw_dir")),
            profile=MOVIE_PROFILE,
            settings=tmp_settings,
            manifest=self.manifest,
            indexer=lambda doc: self.indexed.append(doc.title) or 1,
            chunk_counter=chunk_counter,
        )


def test_tc_nf2002_01_same_question_twice_no_external_work(tmp_settings, item):
    setup = Setup(tmp_settings)
    first = setup.collector.collect(item, "질문1")
    assert first.indexed_titles and "CACHE_HIT" not in first.notices
    llm_calls, source_calls, indexed = (
        len(setup.llm.calls),
        len(setup.source.calls),
        len(setup.indexed),
    )
    stages = []
    second = setup.collector.collect(item, "질문1", on_progress=lambda s, i: stages.append(s))
    assert len(setup.llm.calls) == llm_calls  # P1 · P2 0회
    assert len(setup.source.calls) == source_calls  # 위키 호출 0회
    assert len(setup.indexed) == indexed  # 색인 0회
    assert "CACHE_HIT" in second.notices
    assert stages == ["cache_hit", "done"]


def test_tc_nf2002_02_overlapping_keyword_not_searched_again(tmp_settings, item):
    setup = Setup(tmp_settings)
    setup.collector.collect(item, "질문1")
    before = [arg for name, arg in setup.source.calls if name == "search"]
    report = setup.collector.collect(item, "질문2")
    after = [arg for name, arg in setup.source.calls if name == "search"][len(before) :]
    assert "블랙홀" not in after and "중력" in after
    assert "블랙홀" in report.cached_queries


def test_tc_nf2002_03_same_document_fetched_once(tmp_settings, item):
    setup = Setup(tmp_settings)
    setup.collector.collect(item, "질문1")
    setup.p1["질문2"] = '["웜홀"]'  # 질문2도 「웜홀」 문서를 고른다
    setup.collector.collect(item, "질문2")
    fetched = setup.source.fetched()
    assert fetched.count("4") == 1 and fetched.count("1") == 1  # 항목 자체 문서도 한 번


def test_tc_nf2002_04_failed_search_not_recorded(tmp_settings, item):
    setup = Setup(tmp_settings, mode="api")
    setup.source.fail_calls = 99
    with pytest.raises(ExternalSourceUnavailableError):
        setup.collector.collect(item, "질문1")
    assert not setup.manifest.has_keyword("157336", "블랙홀")
    assert setup.manifest.cached_queries("157336", "질문1") is None


def test_tc_nf2002_08_cache_ignored_when_no_chunks(tmp_settings, item):
    counts = {"157336": 0}
    setup = Setup(tmp_settings, chunk_counter=lambda item_id: counts[item_id])
    setup.collector.collect(item, "질문1")
    report = setup.collector.collect(item, "질문1")  # 매니페스트는 있지만 색인이 비었다
    assert "CACHE_HIT" not in report.notices and report.indexed_titles


def test_tc_nf2002_06_cache_survives_new_collector(tmp_settings, item):
    Setup(tmp_settings).collector.collect(item, "질문1")
    fresh = Setup(tmp_settings)  # 앱 재시작
    report = fresh.collector.collect(item, "질문1")
    assert "CACHE_HIT" in report.notices and fresh.source.calls == []
