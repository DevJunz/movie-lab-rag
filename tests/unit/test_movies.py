"""SPEC-F2001 영화 메타데이터 적재 — 로드와 색인 텍스트 구성."""

from __future__ import annotations

import json
from pathlib import Path

from movielab.core.types import ItemRecord
from movielab.data.movies import load_items, to_index_text, to_item_record

EXPECTED_LABELS = ["제목", "원제", "장르", "감독", "출연", "제작 국가", "원어", "줄거리"]


def _movie(**overrides) -> dict:
    movie = {
        "movie_id": "157336",
        "title": "인터스텔라",
        "original_title": "Interstellar",
        "release_date": "2014-11-05",
        "year": 2014,
        "genres": ["모험", "드라마", "SF"],
        "director": ["크리스토퍼 놀란"],
        "cast": ["배우 갑", "배우 을"],
        "overview": "[합성] 우주 비행사가 웜홀을 지나 새 행성을 찾는다.",
        "runtime": 169,
        "original_language": "en",
        "production_countries": ["United Kingdom", "United States of America"],
        "vote_average": 8.485,
        "vote_count": 40867,
        "tmdb_url": "https://www.themoviedb.org/movie/157336",
    }
    movie.update(overrides)
    return movie


def test_tc_f2001_01_index_text_has_all_labels_in_order():
    lines = to_index_text(_movie()).splitlines()
    assert [line.split(":")[0] for line in lines] == EXPECTED_LABELS
    assert lines == [
        "제목: 인터스텔라 (2014)",
        "원제: Interstellar",
        "장르: 모험, 드라마, SF",
        "감독: 크리스토퍼 놀란",
        "출연: 배우 갑, 배우 을",
        "제작 국가: United Kingdom, United States of America",
        "원어: en (해외 영화)",
        "줄거리: [합성] 우주 비행사가 웜홀을 지나 새 행성을 찾는다.",
    ]


def test_tc_f2001_02_empty_director_written_as_unknown():
    text = to_index_text(_movie(director=[]))
    assert "감독: 정보 없음" in text.splitlines()


def test_tc_f2001_03_original_language_marks_korean_films():
    assert "원어: ko (한국 영화)" in to_index_text(_movie(original_language="ko"))
    assert "원어: en (해외 영화)" in to_index_text(_movie(original_language="en"))


def test_tc_f2001_04_missing_required_field_is_skipped(tmp_path: Path):
    movies = [_movie(), _movie(movie_id="2", overview=""), _movie(movie_id="3")]
    del movies[2]["year"]
    movies.append(_movie(movie_id="4"))
    path = tmp_path / "movies.json"
    path.write_text(json.dumps(movies, ensure_ascii=False), encoding="utf-8")
    result = load_items(path)
    assert [item.item_id for item in result.items] == ["157336", "4"]
    assert result.skipped == 2


def test_tc_f2001_05_movie_id_normalized_to_str_and_duplicates_dropped(tmp_path: Path):
    movies = [_movie(movie_id=123), _movie(movie_id="123", title="중복")]
    path = tmp_path / "movies.json"
    path.write_text(json.dumps(movies, ensure_ascii=False), encoding="utf-8")
    result = load_items(path)
    assert [item.item_id for item in result.items] == ["123"]
    assert result.items[0].title == "인터스텔라"
    assert result.skipped == 1


def test_tc_f2001_01_item_record_fields_and_metadata():
    record = to_item_record(_movie())
    assert isinstance(record, ItemRecord)
    assert (record.item_id, record.title, record.year) == ("157336", "인터스텔라", 2014)
    assert record.url == "https://www.themoviedb.org/movie/157336"
    assert record.index_text == to_index_text(_movie())
    meta = record.metadata
    assert meta["movie_id"] == "157336" and isinstance(meta["year"], int)
    assert meta["genres"] == "모험, 드라마, SF"  # 목록은 문자열로 (F2002 AC-06)
    assert meta["director"] == "크리스토퍼 놀란"
    assert meta["original_language"] == "en"
    assert meta["url"] == "https://www.themoviedb.org/movie/157336"
    assert meta["source_kind"] == "meta" and meta["source_type"] == "영화 메타데이터"
    assert all(isinstance(v, (str, int, float, bool)) for v in meta.values())


def test_tc_f2001_01_fixture_loads(movies_small_path: Path):
    result = load_items(movies_small_path)
    assert len(result.items) == 12 and result.skipped == 0
    assert "감독: 정보 없음" in next(i for i in result.items if i.item_id == "1084390").index_text


def test_tc_f2001_11_null_and_blank_values_become_unknown():
    text = to_index_text(_movie(director=[None, "  "], cast=None))
    assert "감독: 정보 없음" in text.splitlines()
    assert "출연: 정보 없음" in text.splitlines()


def test_tc_f2001_11_language_normalized():
    assert "원어: ko (한국 영화)" in to_index_text(_movie(original_language="KO"))
    assert "원어: 정보 없음" in to_index_text(_movie(original_language=None))
    movie = _movie()
    del movie["original_language"]
    assert "원어: 정보 없음" in to_index_text(movie)


def test_tc_f2001_11_bad_values_skipped_not_fatal(tmp_path: Path):
    movies = [
        _movie(movie_id="1"),
        _movie(movie_id="2", title="   "),
        _movie(movie_id="3", year="미상"),
        _movie(movie_id="4", runtime="169분"),
        _movie(movie_id="5", vote_average="높음"),
        _movie(movie_id="6", year=2014.0),
    ]
    path = tmp_path / "movies.json"
    path.write_text(json.dumps(movies, ensure_ascii=False), encoding="utf-8")
    result = load_items(path)
    assert [item.item_id for item in result.items] == ["1", "6"]
    assert result.skipped == 4
    six = result.items[1]
    assert six.year == 2014 and six.index_text.startswith("제목: 인터스텔라 (2014)\n")


def test_tc_f2001_12_non_array_json_is_format_error(tmp_path: Path):
    import pytest

    from movielab.core.errors import DataFormatError

    path = tmp_path / "movies.json"
    path.write_text('{"movie_id": "1"}', encoding="utf-8")
    with pytest.raises(DataFormatError) as error:
        load_items(path)
    assert error.value.code == "DATA_INVALID"
    path.write_text("[{깨진 json", encoding="utf-8")
    with pytest.raises(DataFormatError):
        load_items(path)
