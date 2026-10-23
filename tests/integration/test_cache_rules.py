"""SPEC-NF2002 (PR #31 리뷰) — 완전 성공 시에만 기록, 색인이 비면 영화 캐시 초기화."""

from __future__ import annotations

import pytest

from movielab.collect.collector import Collector
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from tests.fakes import FakeChatModel, make_manifest, pick_titles
from tests.fakes.source import FakeSource, make_doc

ITEM_INTRO = "[합성] 인터스텔라는 2014년 개봉한 크리스토퍼 놀란 감독의 SF 영화이다."


@pytest.fixture
def item(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _setup(settings, *, indexer="default", chunk_counter=None):
    source = FakeSource()
    source.add(make_doc("1", "인터스텔라"), title_intro=ITEM_INTRO)
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    source.add(make_doc("4", "웜홀"), queries=["블랙홀"])
    llm = FakeChatModel(
        rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀", "웜홀")}
    )
    manifest = make_manifest(settings.path("manifest"))
    collector = Collector(
        api_source=source,
        bundle_source=FakeSource("bundle"),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, settings),
        raw_store=RawStore(settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=settings,
        manifest=manifest,
        indexer=(lambda doc: 1) if indexer == "default" else indexer,
        chunk_counter=chunk_counter,
    )
    return collector, source, manifest


def test_tc_nf2002_11_failed_document_retried_on_next_ask(tmp_settings, item):
    collector, source, manifest = _setup(tmp_settings)
    original = source.fetch
    state = {"fail": True}

    def flaky(page_id):
        if page_id == "4" and state["fail"]:
            raise RuntimeError("일시 오류")
        return original(page_id)

    source.fetch = flaky
    first = collector.collect(item, "블랙홀은?")
    assert any(r.reason == "fetch_failed" for r in first.rejected)
    assert manifest.cached_queries("157336", "블랙홀은?") is None
    assert not manifest.has_keyword("157336", "블랙홀")
    assert manifest.has_page("157336", "2")  # 성공한 문서는 기록

    state["fail"] = False
    second = collector.collect(item, "블랙홀은?")
    assert "CACHE_HIT" not in second.notices
    assert "웜홀" in second.indexed_titles  # 실패했던 문서를 다시 시도
    assert source.fetched().count("2") == 1  # 성공했던 문서는 다시 받지 않음


def test_tc_nf2002_11_no_indexer_records_nothing(tmp_settings, item):
    collector, _, manifest = _setup(tmp_settings, indexer=None)
    collector.collect(item, "블랙홀은?")
    assert manifest.cached_queries("157336", "블랙홀은?") is None
    assert not manifest.has_page("157336", "2")
    assert not manifest.has_keyword("157336", "블랙홀")


def test_tc_nf2002_12_empty_index_resets_movie_cache_for_new_question(tmp_settings, item):
    counts = {"157336": 1}
    collector, source, manifest = _setup(tmp_settings, chunk_counter=lambda i: counts[i])
    collector.collect(item, "블랙홀은?")
    assert manifest.has_page("157336", "1")
    counts["157336"] = 0  # data/chroma를 지운 상황
    report = collector.collect(item, "완전히 새로운 질문")
    assert "인터스텔라" in report.indexed_titles  # 항목 자체 문서까지 다시 수집
    assert source.fetched().count("1") == 2


def test_tc_nf2002_20_failed_reset_distrusts_cache(tmp_settings, item):
    from movielab.collect.manifest import FileLock

    collector, source, manifest = _setup(tmp_settings, chunk_counter=lambda i: 0)
    collector.collect(item, "블랙홀은?")
    assert manifest.cached_queries("157336", "블랙홀은?") is not None
    holder = FileLock(manifest.lock_path, poll_sec=0.01)
    assert holder.acquire()  # 초기화를 못 하게 막는다
    try:
        again = collector.collect(item, "블랙홀은?")
    finally:
        holder.release()
    assert "CACHE_HIT" not in again.notices  # 옛 기록을 믿지 않고 다시 수집
    assert source.fetched().count("2") == 2


def test_tc_nf2002_20_reset_cache_script_reports_failure(
    tmp_settings, tmp_path, monkeypatch, capsys
):
    import json

    from movielab.collect.manifest import FileLock
    from scripts import collect

    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["cache"]["lock_timeout_sec"] = 0
    path = tmp_path / "settings_nowait.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    holder = FileLock(tmp_settings.path("manifest").with_name("manifest.json.lock"), poll_sec=0.01)
    assert holder.acquire()
    try:
        assert collect.main(["--reset-cache"]) == 1
    finally:
        holder.release()
    assert "지우지 못했" in capsys.readouterr().out
    assert collect.main(["--reset-cache"]) == 0
