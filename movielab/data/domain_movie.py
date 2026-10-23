"""영화 도메인 프로필 — 영화에 묶인 문구와 규칙은 이 모듈(과 movielab/data/)에만 둔다."""

from __future__ import annotations

from movielab.core.domain import DomainProfile
from movielab.data import movies

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
    to_index_text=movies.to_index_text,
)
