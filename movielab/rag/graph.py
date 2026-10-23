"""LangGraph RAG 파이프라인 — retrieve · generate 두 노드 (SPEC-F2007, 01-architecture §8).

    START → retrieve → generate → END

`generate`는 작업(`task`)에 맞는 프롬프트를 표(`TASK_PROMPTS`)에서 골라 LLM을 한 번 부른다.
이 SPEC은 `qa`(P3)를 등록하고, 관람 가이드(G1) · 사실 판정(C1)은 SPEC-F2010이 더한다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from movielab.core.domain import DomainProfile
from movielab.core.messages import NOT_FOUND
from movielab.core.types import Evidence
from movielab.prompts import build_answer_prompt

logger = logging.getLogger(__name__)

PromptBuilder = Callable[[DomainProfile, list[Evidence], str], str]

# 작업 → 프롬프트 생성 함수
TASK_PROMPTS: dict[str, PromptBuilder] = {"qa": build_answer_prompt}

_CITATION = re.compile(r"\[근거\s*\d")


class RAGState(TypedDict, total=False):
    movie_id: str
    question: str  # task가 factcheck이면 주장, guide이면 고정 질문
    task: str  # "qa" | "guide" | "factcheck"
    contexts: list[Evidence]  # retrieve가 채움
    no_external: bool  # 외부 근거가 하나도 없음 (F2012 안내)
    answer: str  # generate가 채움 (factcheck은 JSON 문자열)


def is_not_found(answer: str) -> bool:
    """답이 `NOT_FOUND` 문장으로 시작하고 인용이 하나도 없으면 '확인되지 않음' 답이다."""
    text = " ".join(answer.split())
    return text.startswith(NOT_FOUND) and not _CITATION.search(text)


def build_graph(retriever: Any, llm: Any, profile: DomainProfile) -> Any:
    """`retriever.retrieve(item_id, query) -> RetrievalResult`, `llm.invoke(prompt)`."""

    def retrieve(state: RAGState) -> dict[str, Any]:
        result = retriever.retrieve(state["movie_id"], state["question"])
        return {"contexts": result.evidences, "no_external": result.no_external}

    def generate(state: RAGState) -> dict[str, Any]:
        task = state.get("task", "qa")
        builder = TASK_PROMPTS.get(task)
        if builder is None:
            raise ValueError(f"등록되지 않은 작업: {task}")
        prompt = builder(profile, state["contexts"], state["question"])
        logger.debug("%s 프롬프트:\n%s", task, prompt)
        return {"answer": str(llm.invoke(prompt).content)}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
