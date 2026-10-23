"""영화 도메인 프로필 — 영화에 묶인 문구와 규칙은 이 모듈(과 movielab/data/)에만 둔다."""

from __future__ import annotations

from movielab.core.domain import DomainProfile
from movielab.core.types import ItemRecord
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
)
