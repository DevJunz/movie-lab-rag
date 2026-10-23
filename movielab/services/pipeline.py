"""서비스 공용 실행 도우미 — 그래프를 노드 단위로 돌리며 진행 단계를 알린다 (F2012).

질의응답(F2009) · 관람 가이드 · 사실 판정(F2010)이 같이 쓴다. 그래프 노드는 두 개 그대로다(F2007).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Progress = Callable[[str, dict[str, Any]], None]


def run_graph(graph: Any, state: dict[str, Any], on_progress: Progress | None) -> dict[str, Any]:
    """`retrieve` 시작 전에 `retrieve`, `retrieve`가 끝나면 `generate` 단계를 알린다."""

    def notify(stage: str) -> None:
        if on_progress is not None:
            on_progress(stage, {})

    notify("retrieve")
    result = dict(state)
    for update in graph.stream(state, stream_mode="updates"):
        for node, values in update.items():
            result.update(values or {})
            if node == "retrieve":
                notify("generate")
    return result
