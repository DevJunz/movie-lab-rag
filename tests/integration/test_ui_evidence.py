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


def _app(result, profile, preview_chars):
    from movielab.ui.components.evidence import render_evidence

    render_evidence(result, profile, preview_chars=preview_chars)


def _run(result: CitedResult) -> AppTest:
    at = AppTest.from_function(_app, args=(result, MOVIE_PROFILE, 200))
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
    previews = [t.value for e in at.expander for t in e.text]
    assert previews and all(len(p) <= 201 for p in previews)  # 200자 + 줄임표
    assert not at.info


def test_tc_f2008_07_uncited_notice():
    at = _run(CitedResult(cited=[], uncited=True))
    assert [i.value for i in at.info] == ["이 답변에는 인용된 근거가 없습니다."]
    assert "[근거" not in _texts(at)


def test_tc_f2008_06_link_with_parentheses_kept_whole():
    from movielab.ui.components.evidence import evidence_line

    evidence = Evidence(
        n=2,
        chunk_id="c2",
        source_kind="wiki",
        source_type="위키백과",
        title="트리니티 (핵 실험)",
        url="https://ko.wikipedia.org/wiki/트리니티_(핵_실험)",
        license="CC BY-SA 4.0",
        text="[합성]",
    )
    line = evidence_line(evidence, MOVIE_PROFILE)
    assert "%28" in line and "%29" in line and line.rstrip().endswith("CC BY-SA 4.0")
    assert (
        "(https://ko.wikipedia.org/wiki/" in line
        and ")" not in line.split("](", 1)[1].split(")")[0]
    )


def test_tc_f2008_06_title_escaped_and_preview_plain():
    from movielab.ui.components.evidence import evidence_line

    evidence = dataclasses_replace(_evidence(2), title="제목*별[x]", url="https://a.invalid/a b>c")
    line = evidence_line(evidence, MOVIE_PROFILE)
    assert "제목\\*별\\[x\\]" in line and "a%20b%3Ec" in line
    at = _run(
        CitedResult(
            cited=[dataclasses_replace(_evidence(3), text="$100 와 $200 # 제목")], uncited=False
        )
    )
    assert any("$100 와 $200 # 제목" in t.value for t in at.text)


def dataclasses_replace(obj, **kw):
    import dataclasses

    return dataclasses.replace(obj, **kw)
