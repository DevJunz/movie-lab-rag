"""SPEC-F2007 근거 기반 답변 생성 — LangGraph 노드 2개, 작업별 프롬프트, 확인 불가 판정."""

from __future__ import annotations

import pytest

from movielab.core.messages import NOT_FOUND
from movielab.core.types import Evidence, RetrievalResult
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.rag.graph import build_graph, is_not_found
from tests.fakes import FakeChatModel


class FakeRetriever:
    def __init__(self, evidences):
        self.evidences = evidences
        self.calls = []

    def retrieve(self, item_id, query):
        self.calls.append((item_id, query))
        return RetrievalResult(evidences=self.evidences, no_external=len(self.evidences) == 1)


def _evidences():
    return [
        Evidence(1, "157336", "meta", "영화 메타데이터", "인터스텔라 (2014)", "https://t", None,
                 "제목: 인터스텔라 (2014)"),
        Evidence(2, "157336:1:0", "wiki", "위키백과", "블랙홀", "https://w", "CC BY-SA 4.0",
                 "블랙홀은 빛도 빠져나오지 못하는 천체이다.", 0.5),
    ]  # fmt: skip


def test_tc_f2007_01_graph_has_exactly_two_nodes():
    graph = build_graph(FakeRetriever(_evidences()), FakeChatModel(), MOVIE_PROFILE)
    nodes = set(graph.get_graph().nodes)
    assert nodes == {"__start__", "retrieve", "generate", "__end__"}
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert edges == {("__start__", "retrieve"), ("retrieve", "generate"), ("generate", "__end__")}


def test_tc_f2007_06_mermaid_output():
    graph = build_graph(FakeRetriever(_evidences()), FakeChatModel(), MOVIE_PROFILE)
    mermaid = graph.get_graph().draw_mermaid()
    assert "retrieve" in mermaid and "generate" in mermaid


def test_tc_f2007_04_is_not_found():
    assert is_not_found(NOT_FOUND)
    assert is_not_found(f"  {NOT_FOUND}  ")
    assert not is_not_found(f"{NOT_FOUND} 다만 블랙홀은 천체다 [근거 2]")
    assert not is_not_found("블랙홀은 천체다 [근거 2]. 렌즈는 문서에서 확인되지 않습니다.")


def test_tc_f2007_05_unknown_task_rejected():
    graph = build_graph(FakeRetriever(_evidences()), FakeChatModel(), MOVIE_PROFILE)
    with pytest.raises(ValueError):
        graph.invoke({"movie_id": "157336", "question": "q", "task": "없는작업"})
