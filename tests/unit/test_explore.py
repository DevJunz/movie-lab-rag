"""SPEC-F2011 조건 기반 탐색 — where 재검사, 후보 밖 결과 제외, 영화 프로필의 필터 변환."""

from __future__ import annotations

import pytest

from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.services.explore import matches_where

KO_1999 = {"year": 1999, "original_language": "ko"}
EN_1991 = {"year": 1991, "original_language": "en"}
KO_2019 = {"year": 2019, "original_language": "ko"}


@pytest.mark.parametrize(
    ("where", "meta", "expected"),
    [
        (None, EN_1991, True),
        ({"year": {"$gte": 1990}}, KO_1999, True),
        ({"year": {"$lte": 1999}}, KO_2019, False),
        ({"original_language": {"$eq": "ko"}}, EN_1991, False),
        ({"original_language": "ko"}, KO_1999, True),
        ({"$and": [{"year": {"$gte": 1990}}, {"year": {"$lte": 1999}}]}, KO_2019, False),
        ({"year": {"$gte": 1990}}, {"original_language": "ko"}, False),  # 필드 없음
    ],
)
def test_tc_f2011_08_matches_where(where, meta, expected):
    assert matches_where(meta, where) is expected


def test_tc_f2011_08_movie_profile_explore_where():
    where = MOVIE_PROFILE.explore_where({"year_min": 1990, "year_max": 1999, "korean_only": True})
    assert matches_where(KO_1999, where)
    assert not matches_where(EN_1991, where) and not matches_where(KO_2019, where)
    assert MOVIE_PROFILE.explore_where({"year_min": None, "korean_only": None}) is None
    only_min = MOVIE_PROFILE.explore_where({"year_min": 2000})
    assert matches_where(KO_2019, only_min) and not matches_where(KO_1999, only_min)
    # 잘못된 값(문자열 연도 · 불리언 아님)은 조건으로 쓰지 않는다
    assert MOVIE_PROFILE.explore_where({"year_min": "1990년", "korean_only": "yes"}) is None
