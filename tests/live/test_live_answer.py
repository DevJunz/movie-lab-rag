"""SPEC-F2007 TC-06 · 07 — 실제 GMS로 답변 생성 (`pytest -m live`, 실제 data/chroma 색인 사용).

TC-07은 근거 문서에 답이 있는 Q4로 검증한다 (SPEC-F2007 §7.1).
"""

from __future__ import annotations

import re

import pytest

from movielab.config import load_settings
from movielab.container import build_services
from movielab.rag.graph import build_graph, is_not_found

pytestmark = pytest.mark.live


def _graph(movie_id: str = "157336"):
    services = build_services(load_settings())
    if services.store.count_where("wiki_docs", {"movie_id": movie_id}) == 0:
        pytest.skip(f"{movie_id} 위키 청크가 색인되어 있지 않다 (scripts.collect 먼저)")
    return build_graph(services.retriever(), services.llm, services.profile)


def test_tc_f2007_07_q4_answer_cites_evidence():
    state = _graph("872585").invoke(
        {"movie_id": "872585", "question": "트리니티 핵 실험은 언제 어디서 진행되었나?",
         "task": "qa"}
    )  # fmt: skip
    print(state["answer"])
    assert re.search(r"\[근거\s*\d+", state["answer"])


def test_tc_f2007_06_q6_not_found():
    state = _graph().invoke(
        {"movie_id": "157336", "question": "이 영화 촬영에 쓴 카메라 렌즈의 모델명은 무엇인가?",
         "task": "qa"}
    )  # fmt: skip
    print(state["answer"])
    assert is_not_found(state["answer"]) or "확인되지 않" in state["answer"]
