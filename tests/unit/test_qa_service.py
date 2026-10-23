"""SPEC-F2009 §3.3 — QAService.ask: 수집 → 그래프 → 인용 선별."""

from __future__ import annotations

import pytest

from movielab.core.errors import ItemNotFoundError
from movielab.core.types import CollectReport, Evidence
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.qa import QAService
from tests.fakes import FakeClock


def _evidence(n: int) -> Evidence:
    return Evidence(
        n=n, chunk_id=f"c{n}", source_kind="wiki", source_type="위키백과", title=f"문서{n}",
        url=f"https://example.invalid/{n}", license="CC BY-SA 4.0", text="[합성] 본문",
    )  # fmt: skip


class FakeCollector:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.calls: list[tuple[str, str]] = []

    def collect(self, item, question, on_progress=None):
        self.log.append("collect")
        self.calls.append((item.item_id, question))
        if on_progress is not None:
            on_progress("done", {"titles": ["블랙홀"], "rejected": 0})
        return CollectReport(item_id=item.item_id, question=question, notices=["CACHE_HIT"])


class FakeGraph:
    def __init__(self, log: list[str], answer: str) -> None:
        self.log = log
        self.answer = answer
        self.states: list[dict] = []

    def invoke(self, state):
        self.log.append("graph")
        self.states.append(dict(state))
        return {**state, "contexts": [_evidence(n) for n in (1, 2, 3)], "answer": self.answer}


@pytest.fixture
def catalog(movies_small_path):
    return Catalog(lambda: load_items(movies_small_path))


def _service(catalog, answer):
    log: list[str] = []
    collector, graph = FakeCollector(log), FakeGraph(log, answer)
    clock = FakeClock()
    service = QAService(catalog, collector, graph, clock=clock.monotonic)
    return service, collector, graph, log


def test_tc_f2009_05_ask_collects_then_answers_with_citations(catalog):
    service, collector, graph, log = _service(catalog, "가 [근거 3]. 나 [근거 1].")
    stages = []
    result = service.ask("157336", "블랙홀은?", on_progress=lambda s, info: stages.append(s))
    assert log == ["collect", "graph"]
    assert collector.calls == [("157336", "블랙홀은?")]
    assert graph.states == [{"movie_id": "157336", "question": "블랙홀은?", "task": "qa"}]
    assert [e.n for e in result.cited] == [1, 3] and result.uncited is False
    assert [e.n for e in result.evidences] == [1, 2, 3]
    assert result.not_found is False
    assert result.collect.notices == ["CACHE_HIT"]
    assert set(result.timings) >= {"collect", "total"}
    assert stages == ["done"]  # 진행 상태 콜백은 수집기에 그대로 넘긴다


def test_tc_f2009_05_not_found_answer(catalog):
    service, *_ = _service(catalog, "제공된 문서에서 확인되지 않습니다.")
    result = service.ask("157336", "렌즈 모델명은?")
    assert result.not_found is True and result.uncited is True and result.cited == []


def test_tc_f2009_05_unknown_item(catalog):
    service, collector, _, log = _service(catalog, "")
    with pytest.raises(ItemNotFoundError):
        service.ask("0", "질문")
    assert log == []
