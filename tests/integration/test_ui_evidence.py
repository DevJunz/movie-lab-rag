"""SPEC-F2008 근거 목록 컴포넌트 — Streamlit `AppTest`로 그린 결과를 검사한다."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from movielab.core.types import CitedResult, Evidence
from movielab.data.domain_movie import MOVIE_PROFILE


def _evidence(n: int, *, meta: bool = False) -> Evidence:
    return Evidence(
        n=n,
        chunk_id=f"c{n}",
        source_kind="meta" if meta else "wiki",
        source_type="영화 메타데이터" if meta else "위키백과",
        title="인터스텔라 (2014)" if meta else f"문서{n}",
        url=f"https://example.invalid/{n}",
        license=None if meta else "CC BY-SA 4.0",
        text="[합성] " + "본문 " * 100,
    )


def _app(result, profile):
    from movielab.ui.components.evidence import render_evidence

    render_evidence(result, profile)


def _run(result: CitedResult) -> AppTest:
    at = AppTest.from_function(_app, args=(result, MOVIE_PROFILE))
    at.run()
    assert not at.exception
    return at


def _texts(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_tc_f2008_06_only_cited_with_link_type_license():
    result = CitedResult(cited=[_evidence(1, meta=True), _evidence(3)], uncited=False)
    at = _run(result)
    text = _texts(at)
    assert "[근거 1]" in text and "[근거 3]" in text
    assert "[근거 2]" not in text and "[근거 4]" not in text
    assert "영화 메타데이터" in text and "위키백과" in text
    assert "https://example.invalid/1" in text and "https://example.invalid/3" in text
    assert "TMDB" in text and "원문" in text
    assert text.count("CC BY-SA 4.0") == 1  # 라이선스는 위키백과 근거에만
    assert len(at.expander) == 2  # 근거마다 본문 미리보기
    assert not at.info


def test_tc_f2008_07_uncited_notice():
    at = _run(CitedResult(cited=[], uncited=True))
    assert [i.value for i in at.info] == ["이 답변에는 인용된 근거가 없습니다."]
    assert "[근거" not in _texts(at)
