"""SPEC-F2004 TC-10 — 제공 묶음 소스로도 P1 → 검색 → P2 → 수집 → (색인) 절차가 그대로 돈다."""

from __future__ import annotations

from movielab.collect.collector import Collector
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from movielab.data.wiki_bundle import WikiBundleSource
from tests.fakes import FakeChatModel


def test_tc_f2004_10_bundle_source_full_procedure(tmp_settings, movies_small_path, wiki_small_dir):
    tmp_settings.raw["collect"]["source"] = "bundle"
    item = next(i for i in load_items(movies_small_path).items if i.item_id == "157336")
    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀", "웜홀"]', "후보 선별": "[0, 1]"})
    indexed = []
    collector = Collector(
        api_source=None,
        bundle_source=WikiBundleSource(wiki_small_dir),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
        indexer=lambda doc: indexed.append(doc.title) or 2,
    )
    report = collector.collect(item, "블랙홀 묘사는 실제 물리와 얼마나 다른가?")
    assert llm.prompts_for("검색어 추출") and llm.prompts_for("후보 선별")
    assert report.source_used == "bundle"
    assert report.item_doc_title == "인터스텔라"
    assert report.indexed_titles[0] == "인터스텔라"
    assert {"블랙홀", "웜홀"} <= set(report.indexed_titles)
    assert indexed == report.indexed_titles
    saved = RawStore(tmp_settings.path("raw_dir")).load("157336", "9002")
    assert saved.related_movie == "인터스텔라" and saved.search_query == "블랙홀"
