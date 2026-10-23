"""SPEC-NF2005 AC-04 — 테스트용 DomainProfile을 주입하면 다른 도메인 문구로 동작한다."""

from __future__ import annotations

from movielab.core.domain import DomainProfile
from movielab.data.domain_movie import MOVIE_PROFILE

BOOK_PROFILE = DomainProfile(
    item_label="도서",
    expert_role="도서 큐레이터",
    assistant_role="도서 지식 도우미",
    meta_source_label="도서 메타데이터",
    doc_source_label="위키백과",
    meta_link_label="출판사",
    attribution_notice="도서 정보: 테스트",
)

TEMPLATE = (
    "너는 {expert_role}이다. "
    "{item_label}에 대해 {meta_source_label}와 {doc_source_label}만 근거로 답한다."
)


def test_tc_nf2005_05_book_profile_renders_without_movie_words():
    text = BOOK_PROFILE.render(TEMPLATE)
    assert "도서 큐레이터" in text and "도서 메타데이터" in text
    assert "영화" not in text


def test_tc_nf2005_05_movie_profile_renders_movie_words():
    text = MOVIE_PROFILE.render(TEMPLATE)
    assert "영화 큐레이터" in text and "영화 메타데이터" in text
    assert MOVIE_PROFILE.disclaimer is None  # A-16


def test_tc_nf2005_05_render_keeps_extra_fields():
    assert BOOK_PROFILE.render("{item_label}: {title}", title="데미안") == "도서: 데미안"
