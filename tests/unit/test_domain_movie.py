"""영화 도메인 프로필 규칙 — 항목 카드, 항목 자체 문서 검색어 (SPEC-F2003)."""

from __future__ import annotations

from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items


def _items(path):
    return {i.item_id: i for i in load_items(path).items}


def test_tc_f2003_07_same_title_movies_get_year_specific_queries(movies_small_path):
    items = _items(movies_small_path)
    q1991 = MOVIE_PROFILE.item_doc_queries(items["10020"])
    q2017 = MOVIE_PROFILE.item_doc_queries(items["321612"])
    assert q1991[0] == "미녀와 야수 (1991년 영화)"
    assert q2017[0] == "미녀와 야수 (2017년 영화)"
    assert q1991[1:] == q2017[1:] == ["미녀와 야수 (영화)", "미녀와 야수"]


def test_tc_f2003_01_item_card_summarizes_movie(movies_small_path):
    item = _items(movies_small_path)["157336"]
    card = MOVIE_PROFILE.item_card(item)
    assert card.startswith("인터스텔라 (2014) / 원제: Interstellar / 감독: 크리스토퍼 놀란")
    assert "장르: 모험, 드라마, SF" in card
    assert "줄거리(앞부분): [합성]" in card
    assert "\n" not in card


def test_tc_f2003_01_item_card_truncates_long_overview(movies_small_path):
    import dataclasses

    item = _items(movies_small_path)["157336"]
    long_text = item.index_text.replace("줄거리: ", "줄거리: " + "가" * 1000)
    card = MOVIE_PROFILE.item_card(dataclasses.replace(item, index_text=long_text))
    overview = card.split("줄거리(앞부분): ")[1]
    assert len(overview) <= 301 and overview.endswith("…")
