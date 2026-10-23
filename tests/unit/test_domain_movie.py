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
    card = MOVIE_PROFILE.item_card(item, 300)
    assert card.startswith("인터스텔라 (2014) / 원제: Interstellar / 감독: 크리스토퍼 놀란")
    assert "장르: 모험, 드라마, SF" in card
    assert "줄거리(앞부분): [합성]" in card
    assert "\n" not in card


def test_tc_f2003_11_item_card_truncates_by_setting(movies_small_path):
    import dataclasses

    item = _items(movies_small_path)["157336"]
    long_text = item.index_text.replace("줄거리: ", "줄거리: " + "가" * 1000)
    card = MOVIE_PROFILE.item_card(dataclasses.replace(item, index_text=long_text), 50)
    overview = card.split("줄거리(앞부분): ")[1]
    assert len(overview) == 51 and overview.endswith("…")


def test_tc_f2003_11_multi_paragraph_overview_kept(movies_small_path):
    import dataclasses

    item = _items(movies_small_path)["157336"]
    text = item.index_text.replace("줄거리: ", "줄거리: 첫 문단.\n\n둘째 문단에 웜홀이 나온다. ")
    card = MOVIE_PROFILE.item_card(dataclasses.replace(item, index_text=text), 300)
    assert "둘째 문단에 웜홀" in card and "\n" not in card


# --- SPEC-F2004 §3.4 항목 자체 문서 판별 ---


def _cand(title, requested, intro, disambiguation=False, page_id="1"):
    from movielab.core.types import Candidate

    return Candidate(
        page_id=page_id, title=title, snippet=intro, matched_title=requested,
        disambiguation=disambiguation,
    )  # fmt: skip


def test_tc_f2004_05_year_variant_preferred_over_plain_title(movies_small_path):
    item = _items(movies_small_path)["321612"]
    resolved = [
        _cand(
            "미녀와 야수 (2017년 영화)",
            "미녀와 야수 (2017년 영화)",
            "2017년 영화이다.",
            page_id="11",
        ),
        _cand(
            "미녀와 야수", "미녀와 야수", "18세기 프랑스 동화이다. 영화로 각색되었다.", page_id="10"
        ),
    ]
    assert MOVIE_PROFILE.pick_item_doc(item, resolved).page_id == "11"


def test_tc_f2004_05_plain_title_rejected_when_variant_exists_elsewhere(movies_small_path):
    item = _items(movies_small_path)[
        "10020"
    ]  # 1991년 — 1991 표제가 없고 2017 표제만 있는 상황 가정
    resolved = [_cand("미녀와 야수", "미녀와 야수", "18세기 프랑스의 동화이다.")]
    assert MOVIE_PROFILE.pick_item_doc(item, resolved) is None


def test_tc_f2004_06_plain_title_needs_film_evidence(movies_small_path):
    item = _items(movies_small_path)["157336"]
    ok = _cand("인터스텔라", "인터스텔라", "인터스텔라는 2014년 개봉한 SF 영화이다.")
    by_director = _cand("인터스텔라", "인터스텔라", "크리스토퍼 놀란이 만든 영화이다.")
    no_film = _cand("인터스텔라", "인터스텔라", "인터스텔라는 2014년의 음반이다.")
    assert MOVIE_PROFILE.pick_item_doc(item, [ok]) is not None
    assert MOVIE_PROFILE.pick_item_doc(item, [by_director]) is not None
    assert MOVIE_PROFILE.pick_item_doc(item, [no_film]) is None


def test_tc_f2004_06_redirected_variant_accepted(movies_small_path):
    item = _items(movies_small_path)["157336"]
    # 「인터스텔라 (영화)」가 「인터스텔라」로 넘겨주기됨 — 영화 전용 표제로 찾았으므로 채택
    redirected = _cand("인터스텔라", "인터스텔라 (영화)", "아무 도입부")
    assert MOVIE_PROFILE.pick_item_doc(item, [redirected]).title == "인터스텔라"


def test_tc_f2004_06_disambiguation_never_item_doc(movies_small_path):
    item = _items(movies_small_path)["1255"]
    dis = _cand("괴물 (동음이의)", "괴물 (영화)", "다음을 가리킨다", disambiguation=True)
    assert MOVIE_PROFILE.pick_item_doc(item, [dis]) is None
