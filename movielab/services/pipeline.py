"""서비스 공용 실행 도우미 — 그래프를 노드 단위로 돌리며 단계를 알리고 시간을 잰다 (F2012, NF2001).

질의응답(F2009) · 관람 가이드 · 사실 판정(F2010)이 같이 쓴다. 그래프 노드는 두 개 그대로다(F2007).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

Progress = Callable[[str, dict[str, Any]], None]


def run_graph(
    graph: Any,
    state: dict[str, Any],
    on_progress: Progress | None,
    *,
    timings: dict[str, float] | None = None,
    clock: Callable[[], float] = time.perf_counter,
) -> dict[str, Any]:
    """`retrieve` 시작 전에 `retrieve`, 끝나면 `generate` 단계를 알린다.

    `timings`를 주면 노드가 끝난 시각으로 `retrieve` · `generate` 소요 시간(초)을 채운다.
    """

    def notify(stage: str) -> None:
        if on_progress is not None:
            on_progress(stage, {})

    notify("retrieve")
    result = dict(state)
    mark = clock()
    for update in graph.stream(state, stream_mode="updates"):
        for node, values in update.items():
            result.update(values or {})
            now = clock()
            if timings is not None and node in ("retrieve", "generate"):
                timings[node] = now - mark
            mark = now
            if node == "retrieve":
                notify("generate")
    return result
