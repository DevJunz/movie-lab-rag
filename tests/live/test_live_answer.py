"""SPEC-F2007 TC-06 · 07 — 실제 GMS로 답변 생성 (`pytest -m live`, 실제 data/chroma 색인 사용)."""

from __future__ import annotations

import re

import pytest

from movielab.config import load_settings
from movielab.container import build_services
from movielab.rag.graph import build_graph, is_not_found

pytestmark = pytest.mark.live


def _graph():
    services = build_services(load_settings())
    if services.store.count_where("wiki_docs", {"movie_id": "157336"}) == 0:
        pytest.skip("인터스텔라 위키 청크가 색인되어 있지 않다 (scripts.collect 먼저)")
    return build_graph(services.retriever(), services.llm, services.profile)


def test_tc_f2007_07_q1_answer_cites_evidence():
    state = _graph().invoke(
        {"movie_id": "157336", "question": "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?",
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
