"""SPEC-F2010 §3.1 관람 가이드 — 인용 선별 · 고정 소제목."""

from __future__ import annotations

import pytest

from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.guide import GUIDE_HEADINGS, GuideService
from tests.fakes.pipeline import FakeCollector, FakeGraph

GUIDE = """## 한 줄 소개
[합성] 우주 탐사 영화다 [근거 1].
## 알고 보면 좋은 배경
[합성] 블랙홀 설명 [근거 3].
## 관람 포인트
[합성] 시간 지연 장면 [근거 1]."""


@pytest.fixture
def catalog(movies_small_path):
    return Catalog(lambda: load_items(movies_small_path))


def test_tc_f2010_01_guide_cites_and_headings(catalog):
    collector, graph = FakeCollector(), FakeGraph(GUIDE)
    result = GuideService(catalog, collector, graph).generate("157336")
    assert [e.n for e in result.cited] == [1, 3] and result.uncited is False
    assert all(heading in result.markdown for heading in GUIDE_HEADINGS)
    request = collector.calls[0][1]
    assert request.startswith("인터스텔라 (2014) 관람 가이드")
    assert graph.states == [{"movie_id": "157336", "question": request, "task": "guide"}]


def test_tc_f2010_12_missing_heading_filled(catalog):
    partial = "## 한 줄 소개\n[합성] 우주 탐사 영화다 [근거 1]."
    result = GuideService(catalog, FakeCollector(), FakeGraph(partial)).generate("157336")
    for heading in GUIDE_HEADINGS:
        assert heading in result.markdown
    tail = result.markdown.split("## 관람 포인트", 1)[1]
    assert "문서에서 확인되지 않습니다" in tail
