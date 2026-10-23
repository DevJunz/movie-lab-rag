"""SPEC-F2010 TC-06 — 실제 수집기(제공 묶음) · 임시 Chroma · 가짜 LLM으로 두 특화 기능 실행."""

from __future__ import annotations

import json

import pytest

from movielab.container import build_services
from movielab.services.indexing import index_catalog
from tests.fakes import FakeChatModel, FakeClock, FakeEmbeddings, pick_titles


@pytest.fixture
def services(tmp_settings):
    tmp_settings.raw["collect"]["source"] = "bundle"
    llm = FakeChatModel(
        rules={
            "검색어 추출": '["블랙홀"]',
            "후보 선별": pick_titles("블랙홀"),
            "관람 가이드": (
                "## 한 줄 소개\n[합성] 소개 [근거 1].\n"
                "## 알고 보면 좋은 배경\n[합성] 배경 [근거 2].\n"
                "## 관람 포인트\n[합성] 포인트 [근거 1]."
            ),
            "사실 판정": json.dumps(
                {"verdict": "사실", "reason": "[합성] 맞다 [근거 1]", "citations": [1]}
            ),
        }
    )
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    return services


def test_tc_f2010_06_guide_goes_through_graph(services):
    result = services.guide.generate("157336")
    prompt = services.llm.prompts_for("관람 가이드")[0]
    assert "[근거 1] (영화 메타데이터) 인터스텔라 (2014)" in prompt  # 검색된 근거 블록
    assert "관람 가이드" in prompt and result.cited
    assert len(result.evidences) <= 1 + 2 * services.settings.retrieval.top_k  # Top-k × 2


def test_tc_f2010_06_factcheck_goes_through_graph(services):
    result = services.factcheck.check("157336", "[합성] 인터스텔라는 2014년 영화다")
    prompt = services.llm.prompts_for("사실 판정")[0]
    assert (
        "[근거 1] (영화 메타데이터)" in prompt
        and "주장: [합성] 인터스텔라는 2014년 영화다" in prompt
    )
    assert result.verdict == "사실" and [e.n for e in result.cited] == [1]
