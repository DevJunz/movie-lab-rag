"""SPEC-F2004 (PR #30 리뷰) — 검색 결과 동음이의 표시, 길이 설정, 주입 날짜, 묶음 순위 · snippet."""

from __future__ import annotations

import json
from datetime import date

from movielab.data.wiki_api import WikiApiSource, WikiHttpClient
from movielab.data.wiki_bundle import WikiBundleSource
from tests.fakes import FakeClock, FakeHttpSession

FETCH = {
    "query": {
        "pages": [
            {
                "pageid": 20671,
                "title": "블랙홀",
                "fullurl": "https://ko.wikipedia.org/wiki/x",
                "extract": "블랙홀은 천체이다.",
            }
        ]
    }
}


def _source(settings, session, today=None):
    clock = FakeClock()
    client = WikiHttpClient(
        settings, "t@example.invalid", session=session, clock=clock.monotonic, sleep=clock.sleep
    )
    return WikiApiSource(client, today=today) if today else WikiApiSource(client)


def test_tc_f2004_20_search_detects_disambiguation_from_pageprops(tmp_settings):
    payload = {
        "query": {
            "search": [
                {"pageid": 5, "title": "괴물", "snippet": "다음을 가리킨다", "size": 300},
                {"pageid": 6, "title": "괴물 (2006년 영화)", "snippet": "영화", "size": 9000},
            ],
            "pages": [
                {"pageid": 5, "title": "괴물", "pageprops": {"disambiguation": ""}},
                {"pageid": 6, "title": "괴물 (2006년 영화)"},
            ],
        }
    }
    session = FakeHttpSession().add({"list": "search"}, payload)
    first, second = _source(tmp_settings, session).search("괴물", limit=5)
    params = session.requests[0]["params"]
    assert params["generator"] == "search" and params["gsrsearch"] == "괴물"
    assert params["prop"] == "pageprops" and params["ppprop"] == "disambiguation"
    assert first.disambiguation and not second.disambiguation


def test_tc_f2004_intro_chars_from_settings(tmp_settings):
    tmp_settings.raw["collect"]["intro_chars"] = 120
    session = FakeHttpSession().add({"redirects": 1}, {"query": {"pages": []}})
    _source(tmp_settings, session).resolve_titles(["인터스텔라"])
    assert session.requests[0]["params"]["exchars"] == 120


def test_tc_f2004_collected_at_uses_injected_today(tmp_settings):
    session = FakeHttpSession().add({"pageids": "20671"}, FETCH)
    source = _source(tmp_settings, session, today=lambda: date(2026, 1, 2))
    assert source.fetch("20671").collected_at == "2026-01-02"


def _bundle(tmp_path, docs):
    folder = tmp_path / "bundle"
    folder.mkdir()
    for doc in docs:
        doc.update(url="https://wiki.example.invalid/x", source="한국어 위키백과", collected_at="d")
        path = folder / f"{doc['page_id']}.json"
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return folder


def test_tc_f2004_21_title_tier_beats_many_body_hits(tmp_path):
    folder = _bundle(
        tmp_path,
        [
            {"page_id": 1, "title": "웜홀 연구사", "text": "[합성] 짧은 본문.", "movie_id": "9"},
            {
                "page_id": 2,
                "title": "우주 잡설",
                "text": "[합성] " + "웜홀 " * 400,
                "movie_id": "1",
            },
        ],
    )
    results = WikiBundleSource(folder).search("웜홀", limit=2, item_id="1")
    assert [c.title for c in results] == ["웜홀 연구사", "우주 잡설"]


def test_tc_f2004_21_snippet_contains_query_despite_whitespace(tmp_path):
    gap = "\n\n== 절 ==\n\n" * 60
    text = "[합성] 머리말." + gap + "핵심 문장에 사건의   지평선이 나온다." + gap
    folder = _bundle(tmp_path, [{"page_id": 3, "title": "블랙홀", "text": text, "movie_id": "1"}])
    source = WikiBundleSource(folder, body_chars=100000)
    (first,) = source.search("사건의 지평선", limit=1)
    assert "사건의   지평선" in first.snippet or "사건의 지평선" in first.snippet
