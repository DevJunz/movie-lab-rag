"""LangGraph RAG 파이프라인 — retrieve · generate 두 노드 (SPEC-F2007, 01-architecture §8).

    START → retrieve → generate → END

`generate`는 작업(`task`)에 맞는 프롬프트를 표에서 골라 LLM을 한 번 부른다.
표는 `build_graph(prompts=…)`로 주입한다 — 기본은 `qa`(P3)이고, 관람 가이드(G1) ·
사실 판정(C1)은 SPEC-F2010이 container에서 더한다. 모듈 전역 상태를 바꾸지 않는다.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from movielab.core.domain import DomainProfile
from movielab.core.messages import NOT_FOUND
from movielab.core.types import Evidence
from movielab.prompts import build_answer_prompt

logger = logging.getLogger(__name__)

PromptBuilder = Callable[[DomainProfile, list[Evidence], str], str]

# 작업 → 프롬프트 생성 함수의 기본 표
DEFAULT_PROMPTS: Mapping[str, PromptBuilder] = {"qa": build_answer_prompt}

_CITATION = re.compile(r"\[근거\s*\d")
_QUOTES = "\"'“”‘’「」『』"


class RAGState(TypedDict, total=False):
    movie_id: str
    question: str  # task가 factcheck이면 주장, guide이면 고정 질문
    task: str  # "qa" | "guide" | "factcheck"
    contexts: list[Evidence]  # retrieve가 채움
    no_external: bool  # 외부 근거가 하나도 없음 (F2006 → F2012 안내)
    answer: str  # generate가 채움 (factcheck은 JSON 문자열)


def is_not_found(answer: str) -> bool:
    """답이 `NOT_FOUND` 문장으로 시작하고 인용이 하나도 없으면 '확인되지 않음' 답이다.

    공백을 정규화하고 앞뒤 따옴표를 뗀다. 끝 마침표는 있어도 없어도 된다.
    """
    text = " ".join(answer.split()).strip(_QUOTES + " ")
    return text.startswith(NOT_FOUND.rstrip(".")) and not _CITATION.search(text)


def build_graph(
    retriever: Any,
    llm: Any,
    profile: DomainProfile,
    prompts: Mapping[str, PromptBuilder] | None = None,
) -> Any:
    """`retriever.retrieve(item_id, query) -> RetrievalResult`, `llm.invoke(prompt)`.

    `prompts`는 작업 → 프롬프트 생성 함수 표 (기본 `DEFAULT_PROMPTS`).
    """
    table = dict(DEFAULT_PROMPTS if prompts is None else prompts)

    def builder_for(state: RAGState) -> PromptBuilder:
        task = state.get("task", "qa")
        if task not in table:
            raise ValueError(f"등록되지 않은 작업: {task}")
        return table[task]

    def retrieve(state: RAGState) -> dict[str, Any]:
        builder_for(state)  # 등록되지 않은 작업은 검색 · 임베딩 호출 전에 거부
        result = retriever.retrieve(state["movie_id"], state["question"])
        return {"contexts": result.evidences, "no_external": result.no_external}

    def generate(state: RAGState) -> dict[str, Any]:
        prompt = builder_for(state)(profile, state["contexts"], state["question"])
        logger.debug("%s 프롬프트:\n%s", state.get("task", "qa"), prompt)
        return {"answer": str(llm.invoke(prompt).content)}

    graph = StateGraph(RAGState)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)
    return graph.compile()
