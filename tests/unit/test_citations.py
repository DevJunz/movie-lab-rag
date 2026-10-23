"""SPEC-F2008 근거 표시 — 인용 추출 · 인용 근거 선별."""

from __future__ import annotations

import logging

from movielab.core.types import Evidence
from movielab.rag.citations import extract_citations, select_cited


def _evidences(count: int) -> list[Evidence]:
    return [
        Evidence(
            n=n,
            chunk_id=f"c{n}",
            source_kind="meta" if n == 1 else "wiki",
            source_type="영화 메타데이터" if n == 1 else "위키백과",
            title=f"문서{n}",
            url=f"https://example.invalid/{n}",
            license=None if n == 1 else "CC BY-SA 4.0",
            text=f"[합성] 근거 {n} 본문",
        )
        for n in range(1, count + 1)
    ]


def test_tc_f2008_01_consecutive_and_repeated():
    assert extract_citations("A [근거 1]. B [근거 3][근거 1].") == [1, 3]


def test_tc_f2008_02_comma_and_no_space():
    assert extract_citations("[근거 1, 3] [근거2]") == [1, 3, 2]


def test_tc_f2008_03_out_of_range_ignored_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        assert extract_citations("X [근거 7] Y [근거 0] Z [근거 2]", count=3) == [2]
    assert any("범위" in r.getMessage() for r in caplog.records)


def test_tc_f2008_04_selects_only_cited_keeping_numbers():
    result = select_cited("가 [근거 4]. 나 [근거 2].", _evidences(5))
    assert [e.n for e in result.cited] == [2, 4]
    assert result.uncited is False


def test_tc_f2008_05_uncited():
    result = select_cited("제공된 문서에서 확인되지 않습니다.", _evidences(3))
    assert result.cited == [] and result.uncited is True
