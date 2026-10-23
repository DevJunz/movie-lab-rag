"""SPEC-NF2005 AC-04 — 테스트용 DomainProfile을 주입하면 다른 도메인 문구로 동작한다."""

from __future__ import annotations

from movielab.data.domain_movie import MOVIE_PROFILE
from tests.fakes import BOOK_PROFILE

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


def test_tc_nf2005_05_render_keeps_json_braces_and_unknown_placeholders():
    template = (
        "[작업: 사실 판정]\n"
        '{item_label} 주장. 출력: {"verdict": "사실", "citations": [1]} {unknown}'
    )
    text = BOOK_PROFILE.render(template)
    assert '{"verdict": "사실", "citations": [1]}' in text
    assert "{unknown}" in text
    assert text.startswith("[작업: 사실 판정]\n도서 주장.")


def test_tc_nf2005_05_query_prompt_uses_book_profile():
    from movielab.prompts import build_query_prompt

    prompt = build_query_prompt(
        BOOK_PROFILE, item_card="데미안 (1919)", question="작가는?", min_queries=3, max_queries=5
    )
    assert "도서 큐레이터" in prompt and "도서: 데미안 (1919)" in prompt
    assert "영화" not in prompt
