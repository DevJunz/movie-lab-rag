"""SPEC-F2004 (PR #30 리뷰) — 문서 단위 실패 격리, 캐시 기록 시점, 프로필 누락, 주입 시계."""

from __future__ import annotations

import dataclasses

import pytest

from movielab.collect.collector import Collector
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.core.errors import MissingApiKeyError
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from tests.fakes import FakeChatModel, FakeClock
from tests.fakes.manifest import RecordingManifest
from tests.fakes.source import FakeSource, make_doc

QUESTION = "블랙홀 묘사는 실제 물리와 얼마나 다른가?"
ITEM_INTRO = "[합성] 인터스텔라는 2014년 개봉한 크리스토퍼 놀란 감독의 SF 영화이다."


@pytest.fixture
def item(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _source(kind="api"):
    source = FakeSource(kind)
    source.add(make_doc("1", "인터스텔라"), queries=["인터스텔라"], title_intro=ITEM_INTRO)
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    source.add(make_doc("4", "웜홀"), queries=["웜홀", "블랙홀"])
    return source


def _collector(settings, source, *, indexer=None, manifest=None, profile=MOVIE_PROFILE,
               bundle=None, p2="[0, 1]"):  # fmt: skip
    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": p2})
    return Collector(
        api_source=source,
        bundle_source=bundle or FakeSource("bundle"),
        extractor=QueryExtractor(llm, profile, settings),
        selector=CandidateSelector(llm, profile, settings),
        raw_store=RawStore(settings.path("raw_dir")),
        profile=profile,
        settings=settings,
        manifest=manifest,
        indexer=indexer,
    )


def test_tc_f2004_19_fetch_error_isolated_to_one_document(tmp_settings, item):
    source = _source()
    original = source.fetch

    def flaky_fetch(page_id):
        if page_id == "4":
            raise RuntimeError("본문 조회 실패")
        return original(page_id)

    source.fetch = flaky_fetch
    report = _collector(tmp_settings, source).collect(item, QUESTION)
    reasons = {r.page_id: r.reason for r in report.rejected}
    assert reasons.get("4") == "fetch_failed"
    assert report.indexed_titles == ["인터스텔라", "블랙홀"]


def test_tc_f2004_19_indexer_error_isolated(tmp_settings, item):
    def indexer(doc):
        if doc.title == "블랙홀":
            raise RuntimeError("색인 실패")
        return 2

    report = _collector(tmp_settings, _source(), indexer=indexer).collect(item, QUESTION)
    reasons = {r.title: r.reason for r in report.rejected}
    assert reasons.get("블랙홀") == "index_failed"
    assert "블랙홀" not in report.indexed_titles and "인터스텔라" in report.indexed_titles


def test_tc_f2004_19_user_error_from_indexer_propagates(tmp_settings, item):
    def indexer(doc):
        raise MissingApiKeyError("키 없음")

    with pytest.raises(MissingApiKeyError):
        _collector(tmp_settings, _source(), indexer=indexer).collect(item, QUESTION)


def test_tc_f2004_22_fallback_keywords_and_empty_docs_not_recorded(tmp_settings, item):
    api = _source()
    api.fail_calls = 99
    manifest = RecordingManifest()
    collector = _collector(
        tmp_settings, api, bundle=_source("bundle"), manifest=manifest, p2="[0]",
        indexer=lambda doc: 3 if doc.title == "인터스텔라" else 0,
    )  # fmt: skip
    report = collector.collect(item, QUESTION)
    assert "SOURCE_FALLBACK" in report.notices
    assert manifest.keywords == []  # 묶음으로 대체해 검색한 검색어는 기록하지 않는다
    assert [page_id for page_id, _ in manifest.pages] == ["1"]  # 청크 0개 문서는 기록하지 않는다


def test_tc_f2004_22_primary_source_keywords_recorded(tmp_settings, item):
    manifest = RecordingManifest()
    _collector(tmp_settings, _source(), manifest=manifest, indexer=lambda d: 1).collect(
        item, QUESTION
    )
    assert "블랙홀" in manifest.keywords


def test_tc_f2004_23_profile_without_item_doc_rules(tmp_settings, item):
    profile = dataclasses.replace(MOVIE_PROFILE, pick_item_doc=None, item_doc_queries=None)
    report = _collector(tmp_settings, _source(), profile=profile).collect(item, QUESTION)
    assert "ITEM_DOC_NOT_FOUND" in report.notices and report.indexed_titles


def test_tc_f2004_timings_use_injected_clock(tmp_settings, item):
    clock = FakeClock()
    collector = _collector(tmp_settings, _source())

    def tick():
        clock.advance(0.5)
        return clock.monotonic()

    collector.clock = tick
    report = collector.collect(item, QUESTION)
    assert report.timings["collect"] == 0.5
