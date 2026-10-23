"""SPEC-F2004 TC-09 — WikiApiSource: 검색 · 제목 조회 · 본문 (가짜 HTTP)."""

from __future__ import annotations

from movielab.data.wiki_api import WikiApiSource, WikiHttpClient
from tests.fakes import FakeClock, FakeHttpSession

SEARCH = {
    "query": {
        "search": [
            {
                "pageid": 20671,
                "title": "블랙홀",
                "snippet": '<span class="searchmatch">블랙홀</span>은 빛도 &amp; 못 나오는',
                "size": 40000,
            },
            {"pageid": 99, "title": "블랙홀 (동음이의)", "snippet": "다음을 가리킨다", "size": 300},
        ]
    }
}
RESOLVE = {
    "query": {
        "normalized": [{"from": "인터스텔라_(영화)", "to": "인터스텔라 (영화)"}],
        "redirects": [{"from": "인터스텔라 (영화)", "to": "인터스텔라"}],
        "pages": [
            {"title": "인터스텔라 (2014년 영화)", "missing": True},
            {
                "pageid": 151821,
                "title": "인터스텔라",
                "fullurl": "https://ko.wikipedia.org/wiki/%EC%9D%B8",
                "extract": "인터스텔라는 2014년 영화이다.",
            },
            {
                "pageid": 77,
                "title": "괴물 (동음이의)",
                "pageprops": {"disambiguation": ""},
                "fullurl": "https://ko.wikipedia.org/wiki/x",
                "extract": "",
            },
        ],
    }
}
FETCH = {
    "query": {
        "pages": [
            {
                "pageid": 20671,
                "title": "블랙홀",
                "fullurl": "https://ko.wikipedia.org/wiki/%EB%B8%94",
                "extract": "블랙홀은 중력이 매우 강한 천체이다.",
            }
        ]
    }
}


def _source(tmp_settings, session):
    clock = FakeClock()
    client = WikiHttpClient(
        tmp_settings, "t@example.invalid", session=session, clock=clock.monotonic, sleep=clock.sleep
    )
    return WikiApiSource(client)


def test_tc_f2004_09_search_strips_html_and_normalizes(tmp_settings):
    session = FakeHttpSession().add({"list": "search"}, SEARCH)
    candidates = _source(tmp_settings, session).search("블랙홀", limit=5)
    params = session.requests[0]["params"]
    assert params["srsearch"] == "블랙홀" and params["srlimit"] == 5 and params["srnamespace"] == 0
    first, second = candidates
    assert first.page_id == "20671" and isinstance(first.page_id, str)
    assert first.snippet == "블랙홀은 빛도 & 못 나오는"
    assert first.query == "블랙홀" and first.size == 40000
    assert second.disambiguation and not first.disambiguation


def test_tc_f2004_09_resolve_titles_follows_redirects(tmp_settings):
    session = FakeHttpSession().add({"redirects": 1}, RESOLVE)
    titles = ["인터스텔라 (2014년 영화)", "인터스텔라 (영화)", "괴물 (동음이의)"]
    found = _source(tmp_settings, session).resolve_titles(titles)
    params = session.requests[0]["params"]
    assert params["titles"] == "|".join(titles) and params["exintro"] == 1
    by_request = {c.matched_title: c for c in found}
    assert "인터스텔라 (2014년 영화)" not in by_request  # 없는 문서
    assert by_request["인터스텔라 (영화)"].title == "인터스텔라"  # 넘겨주기를 따라감
    assert by_request["인터스텔라 (영화)"].snippet.startswith("인터스텔라는 2014년")
    assert by_request["괴물 (동음이의)"].disambiguation


def test_tc_f2004_09_fetch_returns_body_and_url(tmp_settings):
    session = FakeHttpSession().add({"pageids": "20671"}, FETCH)
    doc = _source(tmp_settings, session).fetch("20671")
    assert doc.page_id == "20671" and doc.title == "블랙홀"
    assert doc.url == "https://ko.wikipedia.org/wiki/%EB%B8%94"
    assert doc.text.startswith("블랙홀은") and doc.source == "한국어 위키백과"
    assert doc.license == "CC BY-SA 4.0"
    assert session.requests[0]["params"]["explaintext"] == 1


def test_tc_f2004_09_fetch_missing_page_returns_none(tmp_settings):
    session = FakeHttpSession().add({}, {"query": {"pages": [{"pageid": 1, "missing": True}]}})
    assert _source(tmp_settings, session).fetch("1") is None
