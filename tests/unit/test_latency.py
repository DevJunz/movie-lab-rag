"""SPEC-NF2001 응답 시간 — 단계별 시간 기록."""

from __future__ import annotations

from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.qa import QAService
from tests.fakes.pipeline import FakeCollector, FakeGraph


class TickClock:
    """부를 때마다 1초씩 가는 시계 — 단계 구간이 모두 양수가 되게."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


def test_tc_nf2001_01_timings_recorded(movies_small_path):
    catalog = Catalog(lambda: load_items(movies_small_path))
    service = QAService(catalog, FakeCollector(), FakeGraph("답 [근거 1]"), clock=TickClock())
    result = service.ask("157336", "블랙홀은?")
    assert set(result.timings) >= {"collect", "retrieve", "generate", "total"}
    assert all(value >= 0 for value in result.timings.values())
    parts = result.timings["collect"] + result.timings["retrieve"] + result.timings["generate"]
    assert parts <= result.timings["total"]
