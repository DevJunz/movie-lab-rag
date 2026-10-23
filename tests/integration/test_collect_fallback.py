"""SPEC-F2004 TC-11 · TC-12 — auto 모드에서 API를 못 쓰면 제공 묶음으로 전환."""

from __future__ import annotations

from movielab.collect.collector import Collector
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.container import build_services
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from movielab.data.wiki_bundle import WikiBundleSource
from tests.fakes import FakeChatModel, FakeEmbeddings, FakeHttpSession, pick_titles
from tests.fakes.source import FakeSource

QUESTION = "블랙홀 묘사는 실제 물리와 얼마나 다른가?"


def _item(path):
    return next(i for i in load_items(path).items if i.item_id == "157336")


def _llm():
    return FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀")})


def test_tc_f2004_11_api_failure_switches_to_bundle(
    tmp_settings, movies_small_path, wiki_small_dir
):
    api = FakeSource("api", fail_calls=99)
    llm = _llm()
    collector = Collector(
        api_source=api,
        bundle_source=WikiBundleSource(wiki_small_dir),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
    )
    report = collector.collect(_item(movies_small_path), QUESTION)
    assert report.source_used == "bundle"
    assert "SOURCE_FALLBACK" in report.notices
    assert len(api.calls) == 1  # 첫 실패 뒤로는 API를 다시 부르지 않는다
    assert report.item_doc_title == "인터스텔라" and "블랙홀" in report.indexed_titles


def test_tc_f2004_12_no_contact_uses_bundle_without_api_calls(tmp_settings, movies_small_path):
    session = FakeHttpSession()
    services = build_services(
        tmp_settings, llm=_llm(), http=session, embeddings=FakeEmbeddings()
    )  # WIKI_CONTACT 없음
    report = services.collector.collect(_item(movies_small_path), QUESTION)
    assert session.requests == []
    assert report.source_used == "bundle" and "SOURCE_FALLBACK" in report.notices
    assert report.item_doc_title == "인터스텔라"


def test_tc_f2004_11_api_mode_does_not_fall_back(tmp_settings, movies_small_path, wiki_small_dir):
    import pytest

    from movielab.core.errors import ExternalSourceUnavailableError

    tmp_settings.raw["collect"]["source"] = "api"
    llm = _llm()
    collector = Collector(
        api_source=FakeSource("api", fail_calls=99),
        bundle_source=WikiBundleSource(wiki_small_dir),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
    )
    with pytest.raises(ExternalSourceUnavailableError):
        collector.collect(_item(movies_small_path), QUESTION)
