"""테스트용 도메인 프로필 — 영화가 아닌 도메인으로 바꿔 끼울 수 있는지 검사할 때 쓴다."""

from __future__ import annotations

from movielab.core.domain import DomainProfile

BOOK_PROFILE = DomainProfile(
    item_label="도서",
    expert_role="도서 큐레이터",
    assistant_role="도서 지식 도우미",
    meta_source_label="도서 메타데이터",
    doc_source_label="위키백과",
    meta_link_label="출판사",
    attribution_notice="도서 정보: 테스트",
)
