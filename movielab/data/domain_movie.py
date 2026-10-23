"""영화 도메인 프로필 — 영화에 묶인 문구와 규칙은 이 모듈(과 movielab/data/)에만 둔다."""

from __future__ import annotations

from movielab.core.domain import DomainProfile
from movielab.core.types import Candidate, ItemRecord
from movielab.data import movies


def item_card(item: ItemRecord, overview_chars: int) -> str:
    """프롬프트에 넣는 한 줄 영화 요약 (SPEC-F2003 §3.1). 줄거리는 앞 `overview_chars`자."""
    meta = item.metadata
    overview = " ".join(movies.overview_of(item.index_text).split())
    if len(overview) > overview_chars:
        overview = overview[:overview_chars] + "…"
    parts = [
        item.display_name,
        f"원제: {meta.get('original_title') or movies.UNKNOWN}",
        f"감독: {meta.get('director') or movies.UNKNOWN}",
        f"장르: {meta.get('genres') or movies.UNKNOWN}",
        f"줄거리(앞부분): {overview or movies.UNKNOWN}",
    ]
    return " / ".join(parts)


def item_doc_queries(item: ItemRecord) -> list[str]:
    """영화 자체를 다룬 위키백과 문서의 제목 후보. 동명 작품 표제 형식이 먼저 (SPEC-F2003 §3.2)."""
    return [f"{item.title} ({item.year}년 영화)", f"{item.title} (영화)", item.title]


def _looks_like_film(item: ItemRecord, intro: str) -> bool:
    """도입부에 '영화'가 있고, 개봉 연도나 감독 이름이 있으면 그 영화를 다룬 문서로 본다.

    도입부 길이(`collect.intro_chars`)는 소스가 제목 조회 때 이미 맞춰 넘긴다(A-23).
    """
    if "영화" not in intro:
        return False
    directors = [d.strip() for d in str(item.metadata.get("director", "")).split(",")]
    named = any(d and d != movies.UNKNOWN and d in intro for d in directors)
    return str(item.year) in intro or named


def pick_item_doc(item: ItemRecord, resolved: list[Candidate]) -> Candidate | None:
    """항목 자체 문서 판별 (SPEC-F2004 §3.4).

    `(연도년 영화)` → `(영화)` 표제(넘겨주기 포함)를 먼저 고른다. 괄호 없는 제목은 영화 전용 표제가
    없고 도입부가 그 영화를 다룰 때만 고른다(예: 「미녀와 야수」는 동화 문서라서 고르지 않는다).
    """
    year_title, film_title, plain_title = item_doc_queries(item)
    by_request = {c.matched_title: c for c in resolved if not c.disambiguation}
    for title in (year_title, film_title):
        if title in by_request:
            return by_request[title]
    plain = by_request.get(plain_title)
    if plain is not None and _looks_like_film(item, plain.snippet):
        return plain
    return None


MOVIE_PROFILE = DomainProfile(
    item_label="영화",
    expert_role="영화 큐레이터",
    assistant_role="영화 지식 도우미",
    meta_source_label="영화 메타데이터",
    doc_source_label="위키백과",
    meta_link_label="TMDB",
    attribution_notice=(
        "영화 정보: TMDB · 문서: 한국어 위키백과(CC BY-SA 4.0). "
        "답변은 문서를 바탕으로 생성한 요약이며 원문과 다를 수 있습니다."
    ),
    disclaimer=None,  # 영화는 위험 도메인이 아니다 (A-16)
    load_items=movies.load_items_for,
    to_index_text=movies.to_index_text,
    item_card=item_card,
    item_doc_queries=item_doc_queries,
    pick_item_doc=pick_item_doc,
)
