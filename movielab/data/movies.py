"""movies.json 로드와 영화 1편 → 색인 텍스트 1개 구성 (SPEC-F2001).

줄 순서와 라벨은 이 모듈에 정의하고 `DomainProfile.to_index_text`로 노출한다.
한 편의 잘못된 값 때문에 전체 로드가 실패하지 않도록, 문제가 있는 원소는 건너뛰고 센다.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from movielab.core.errors import DataFormatError, DataNotFoundError
from movielab.core.types import ItemRecord, LoadResult

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("movie_id", "title", "year", "overview")
UNKNOWN = "정보 없음"
META_SOURCE_TYPE = "영화 메타데이터"
KOREAN = "ko"


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _join(values: Any) -> str:
    """목록은 ", "로 잇는다. 비었거나 null · 공백뿐이면 `정보 없음`."""
    if isinstance(values, (list, tuple)):
        cleaned = [_clean(v) for v in values if _clean(v)]
        return ", ".join(cleaned) if cleaned else UNKNOWN
    return _clean(values) or UNKNOWN


def _language(movie: dict[str, Any]) -> str:
    return _clean(movie.get("original_language")).lower()


def _language_line(code: str) -> str:
    if not code:
        return UNKNOWN
    return f"{code} (한국 영화)" if code == KOREAN else f"{code} (해외 영화)"


def _year(movie: dict[str, Any]) -> int:
    """`2014`, `2014.0`, `"2014"`를 2014로. 바꿀 수 없으면 ValueError."""
    return int(float(movie["year"]))


def to_index_text(movie: dict[str, Any]) -> str:
    """사용자가 영화를 찾을 단서를 8줄 텍스트로 묶는다. 평점 · 상영 시간은 넣지 않는다."""
    lines = [
        ("제목", f"{_clean(movie['title'])} ({_year(movie)})"),
        ("원제", _join(movie.get("original_title"))),
        ("장르", _join(movie.get("genres"))),
        ("감독", _join(movie.get("director"))),
        ("출연", _join(movie.get("cast"))),
        ("제작 국가", _join(movie.get("production_countries"))),
        ("원어", _language_line(_language(movie))),
        ("줄거리", _clean(movie["overview"])),
    ]
    return "\n".join(f"{label}: {value}" for label, value in lines)


def to_item_record(movie: dict[str, Any]) -> ItemRecord:
    """숫자 필드를 바꿀 수 없으면 ValueError · TypeError (load_items가 건너뛴다)."""
    movie_id = _clean(movie["movie_id"])
    year = _year(movie)
    url = _clean(movie.get("tmdb_url"))
    metadata: dict[str, Any] = {
        "movie_id": movie_id,
        "title": _clean(movie["title"]),
        "original_title": _clean(movie.get("original_title")),
        "year": year,
        "genres": _join(movie.get("genres")),
        "director": _join(movie.get("director")),
        "cast": _join(movie.get("cast")),
        "original_language": _language(movie),
        "runtime": int(float(movie.get("runtime") or 0)),
        "vote_average": float(movie.get("vote_average") or 0.0),
        "url": url,
        "source_kind": "meta",
        "source_type": META_SOURCE_TYPE,
    }
    return ItemRecord(
        item_id=movie_id,
        title=metadata["title"],
        year=year,
        index_text=to_index_text(movie),
        metadata=metadata,
        url=url,
    )


def load_movies(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise DataNotFoundError(f"영화 데이터 파일이 없다: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"영화 데이터 JSON 오류: {path} ({exc.msg})") from exc
    if not isinstance(data, list):
        raise DataFormatError(f"영화 데이터가 JSON 배열이 아니다: {path}")
    return data


def _missing(movie: Any) -> list[str]:
    if not isinstance(movie, dict):
        return list(REQUIRED_FIELDS)
    return [name for name in REQUIRED_FIELDS if not _clean(movie.get(name))]


def load_items(path: Path) -> LoadResult:
    """문제가 있는 원소와 중복 ID는 건너뛰고 경고한다. 파일 순서를 유지한다."""
    items: list[ItemRecord] = []
    seen: set[str] = set()
    skipped = 0
    for index, movie in enumerate(load_movies(path)):
        missing = _missing(movie)
        if missing:
            logger.warning("영화 %d번 원소 건너뜀: 필수 필드 없음 %s", index, missing)
            skipped += 1
            continue
        try:
            record = to_item_record(movie)
        except (ValueError, TypeError) as exc:
            logger.warning("영화 %d번 원소 건너뜀: 값 변환 실패 (%s)", index, exc)
            skipped += 1
            continue
        if record.item_id in seen:
            logger.warning("중복 movie_id %s 건너뜀 (첫 번째만 사용)", record.item_id)
            skipped += 1
            continue
        seen.add(record.item_id)
        items.append(record)
    return LoadResult(items=items, skipped=skipped)


def load_items_for(settings: Any) -> LoadResult:
    """DomainProfile.load_items — 설정의 영화 데이터 경로로 로드한다."""
    return load_items(settings.path("movies"))
