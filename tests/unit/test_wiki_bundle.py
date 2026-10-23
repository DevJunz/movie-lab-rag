"""SPEC-F2004 TC-17 — 제공 문서 묶음 소스 (합성 묶음 wiki_small)."""

from __future__ import annotations

from movielab.data.wiki_bundle import WikiBundleSource


def test_tc_f2004_17_exact_title_ranks_first_and_page_ids_merged(wiki_small_dir):
    source = WikiBundleSource(wiki_small_dir)
    results = source.search("크리스토퍼 놀란", limit=5, item_id="27205")
    assert results[0].title == "크리스토퍼 놀란"
    assert [c.page_id for c in results].count("9004") == 1  # 두 영화가 공유하는 문서는 하나로
    assert all(isinstance(c.page_id, str) for c in results)


def test_tc_f2004_17_current_item_docs_get_bonus(wiki_small_dir):
    source = WikiBundleSource(wiki_small_dir)
    # "합성 본문"은 모든 문서 본문에 비슷한 횟수로 나온다 — 현재 영화(157336)의 문서가 앞선다
    results = source.search("합성 본문", limit=3, item_id="157336")
    assert {c.page_id for c in results} <= {"9001", "9002", "9003", "9004"}


def test_tc_f2004_17_title_match_outranks_body_match(wiki_small_dir):
    results = WikiBundleSource(wiki_small_dir).search("영화", limit=3, item_id="157336")
    assert all("영화" in c.title for c in results)


def test_tc_f2004_17_no_match_returns_empty(wiki_small_dir):
    assert WikiBundleSource(wiki_small_dir).search("존재하지않는검색어", limit=5) == []


def test_tc_f2004_17_snippet_around_match(wiki_small_dir):
    (first,) = WikiBundleSource(wiki_small_dir).search("사건의 지평선", limit=1)
    assert "사건의 지평선" in first.snippet and len(first.snippet) <= 320


def test_tc_f2004_17_resolve_exact_titles_with_intro(wiki_small_dir):
    source = WikiBundleSource(wiki_small_dir)
    found = source.resolve_titles(
        ["미녀와 야수 (2017년 영화)", "미녀와 야수 (영화)", "미녀와 야수"]
    )
    titles = [c.title for c in found]
    assert titles == ["미녀와 야수 (2017년 영화)", "미녀와 야수"]
    assert found[0].snippet.startswith("[합성] 미녀와 야수는 2017년")
    dis = source.resolve_titles(["괴물 (동음이의)"])
    assert dis[0].disambiguation


def test_tc_f2004_17_fetch_returns_document(wiki_small_dir):
    doc = WikiBundleSource(wiki_small_dir).fetch("9020")
    assert doc.title == "명량 해전" and doc.url.startswith("https://")
    assert doc.source == "한국어 위키백과" and doc.collected_at == "2026-09-01"
    assert WikiBundleSource(wiki_small_dir).fetch("없음") is None
