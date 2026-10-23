"""SPEC-F2004 수집 절차 — 가짜 소스 · 가짜 LLM으로 Collector 동작 검증."""

from __future__ import annotations

import pytest

from movielab.collect.collector import Collector
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.data.raw_store import RawStore
from tests.fakes import FakeChatModel
from tests.fakes.source import FakeSource, make_doc

QUESTION = "블랙홀 묘사는 실제 물리와 얼마나 다른가?"
ITEM_INTRO = "[합성] 인터스텔라는 2014년 개봉한 크리스토퍼 놀란 감독의 SF 영화이다."


@pytest.fixture
def item(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _source() -> FakeSource:
    source = FakeSource()
    source.add(make_doc("1", "인터스텔라"), queries=["인터스텔라"], title_intro=ITEM_INTRO)
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    source.add(make_doc("3", "블랙홀 (음반)"), queries=["블랙홀"])
    source.add(make_doc("4", "웜홀"), queries=["웜홀", "블랙홀"])
    return source


def _collector(tmp_settings, source, *, p1='["블랙홀", "웜홀"]', p2="[0, 2]", indexer=None,
               bundle=None):  # fmt: skip
    llm = FakeChatModel(rules={"검색어 추출": p1, "후보 선별": p2})
    collector = Collector(
        api_source=source,
        bundle_source=bundle or FakeSource("bundle"),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
        indexer=indexer,
    )
    return collector, llm


def test_tc_f2004_01_candidates_merged_by_page_id(tmp_settings, item):
    collector, llm = _collector(tmp_settings, _source())
    report = collector.collect(item, QUESTION)
    ids = [c.page_id for c in report.candidates]
    assert ids.count("4") == 1  # 「웜홀」은 두 검색어에서 나왔지만 한 번만
    assert "1" not in ids  # 항목 자체 문서는 후보가 아니라 강제 포함 대상
    assert set(ids) == {"2", "3", "4"}


def test_tc_f2004_03_only_selected_and_item_doc_fetched(tmp_settings, item):
    collector, llm = _collector(tmp_settings, _source(), p2="[0]")
    source = collector.api_source
    report = collector.collect(item, QUESTION)
    candidates = [c.page_id for c in report.candidates]
    assert source.fetched() == ["1", candidates[0]]
    reasons = {r.page_id: r.reason for r in report.rejected}
    assert all(reasons[pid] == "p2_not_selected" for pid in candidates[1:])
    assert report.indexed_titles[0] == "인터스텔라"


def test_tc_f2004_04_item_doc_bypasses_p2_length_and_limit(tmp_settings, item):
    tmp_settings.raw["collect"]["max_selected_docs"] = 0
    source = _source()
    source.docs["1"] = make_doc("1", "인터스텔라", text="[합성] 짧은 영화 문서")  # 200자 미만
    collector, _ = _collector(tmp_settings, source, p2="[]")
    report = collector.collect(item, QUESTION)
    assert report.item_doc_title == "인터스텔라"
    assert report.indexed_titles == ["인터스텔라"]
    assert source.fetched() == ["1"]


def test_tc_f2004_08_disambiguation_and_short_docs_rejected(tmp_settings, item):
    source = _source()
    source.add(make_doc("5", "블랙홀 (동음이의)"), queries=["블랙홀"])
    source.add(make_doc("6", "사건의 지평선", text="[합성] 짧다."), queries=["웜홀"])
    collector, llm = _collector(tmp_settings, source, p2="[0, 1, 2, 3]")
    report = collector.collect(item, QUESTION)
    reasons = {r.title: r.reason for r in report.rejected}
    assert reasons["블랙홀 (동음이의)"] == "disambiguation"
    assert reasons["사건의 지평선"] == "too_short"
    # 동음이의 문서는 P2 후보 목록에도 나오지 않는다
    (p2_prompt,) = llm.prompts_for("후보 선별")
    assert "블랙홀 (동음이의)" not in p2_prompt


def test_tc_f2004_05_documents_saved_with_context(tmp_settings, item):
    collector, _ = _collector(tmp_settings, _source(), p2="[0]")
    report = collector.collect(item, QUESTION)
    saved = RawStore(tmp_settings.path("raw_dir")).load("157336", "1")
    assert saved.title == "인터스텔라" and saved.movie_id == "157336"
    assert saved.related_movie == "인터스텔라" and saved.is_item_doc
    assert saved.url.startswith("https://") and len(saved.text) > 0
    assert report.saved_paths and all(p.exists() for p in report.saved_paths)


def test_tc_f2004_13_progress_stages_in_order(tmp_settings, item):
    collector, _ = _collector(tmp_settings, _source())
    stages = []
    collector.collect(item, QUESTION, on_progress=lambda stage, info: stages.append(stage))
    expected = ["extract_queries", "resolve_item_doc", "search", "filter", "select", "fetch"]
    expected += ["index", "done"]
    assert [s for i, s in enumerate(stages) if i == 0 or stages[i - 1] != s] == expected


def test_tc_f2004_03_indexer_called_for_each_saved_doc(tmp_settings, item):
    indexed = []
    collector, _ = _collector(
        tmp_settings, _source(), p2="[0]", indexer=lambda doc: indexed.append(doc.title) or 3
    )
    report = collector.collect(item, QUESTION)
    assert indexed == report.indexed_titles and report.indexed_chunks == 3 * len(indexed)


def test_tc_f2004_01_no_candidates_skips_p2(tmp_settings, item):
    source = FakeSource()
    source.add(make_doc("1", "인터스텔라"), title_intro=ITEM_INTRO)
    collector, llm = _collector(tmp_settings, source)
    report = collector.collect(item, QUESTION)
    assert llm.prompts_for("후보 선별") == []
    assert report.indexed_titles == ["인터스텔라"]


def test_tc_f2004_06_item_doc_not_found_notice(tmp_settings, item):
    source = FakeSource()
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    collector, _ = _collector(tmp_settings, source, p2="[0]")
    report = collector.collect(item, QUESTION)
    assert "ITEM_DOC_NOT_FOUND" in report.notices
    assert report.item_doc_title is None and report.indexed_titles == ["블랙홀"]
