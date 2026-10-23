"""서비스 단위 테스트용 가짜 수집기 · 그래프 (질의응답 · 관람 가이드 · 사실 판정 공용)."""

from __future__ import annotations

from typing import Any

from movielab.core.types import CollectReport, Evidence


def make_evidence(n: int, *, meta: bool = False, text: str = "[합성] 근거 본문") -> Evidence:
    return Evidence(
        n=n,
        chunk_id=f"c{n}",
        source_kind="meta" if meta else "wiki",
        source_type="영화 메타데이터" if meta else "위키백과",
        title=f"문서{n}",
        url=f"https://example.invalid/{n}",
        license=None if meta else "CC BY-SA 4.0",
        text=text,
    )


class FakeCollector:
    """`collect(item, question, on_progress)` 호출을 남기고 빈 수집 결과를 돌려준다."""

    def __init__(self, log: list[str] | None = None) -> None:
        self.log = log if log is not None else []
        self.calls: list[tuple[str, str]] = []

    def collect(self, item: Any, question: str, on_progress: Any = None) -> CollectReport:
        self.log.append("collect")
        self.calls.append((item.item_id, question))
        if on_progress is not None:
            on_progress("done", {"titles": [], "rejected": 0})
        return CollectReport(item_id=item.item_id, question=question)


class FakeGraph:
    """LangGraph `stream(stream_mode="updates")`처럼 retrieve · generate 갱신을 낸다."""

    def __init__(
        self, answer: str, evidences: list[Evidence] | None = None, log: list[str] | None = None
    ) -> None:
        self.answer = answer
        self.evidences = evidences or [make_evidence(n, meta=n == 1) for n in (1, 2, 3, 4)]
        self.log = log if log is not None else []
        self.states: list[dict[str, Any]] = []

    def stream(self, state: dict[str, Any], stream_mode: str = "updates") -> Any:
        self.log.append("graph")
        self.states.append(dict(state))
        no_external = all(e.source_kind == "meta" for e in self.evidences)
        yield {"retrieve": {"contexts": self.evidences, "no_external": no_external}}
        yield {"generate": {"answer": self.answer}}

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        result = dict(state)
        for update in self.stream(state):
            for values in update.values():
                result.update(values)
        return result
