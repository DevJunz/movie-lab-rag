"""SPEC-F2010 §3.2 사실 여부 판정 — 라벨 3종, 근거 없는 판정 금지."""

from __future__ import annotations

import json

import pytest

from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.factcheck import FactCheckService
from tests.fakes.pipeline import FakeCollector, FakeGraph

CLAIM = "조선 수군의 배는 12척이었다"


@pytest.fixture
def catalog(movies_small_path):
    return Catalog(lambda: load_items(movies_small_path))


def _check(catalog, answer: str):
    collector, graph = FakeCollector(), FakeGraph(answer)
    result = FactCheckService(catalog, collector, graph).check("282631", CLAIM)
    return result, collector, graph


def test_tc_f2010_02_supported_fact(catalog):
    answer = json.dumps({"verdict": "사실", "reason": "[합성] 12척이다 [근거 2]", "citations": [2]})
    result, collector, graph = _check(catalog, answer)
    assert result.verdict == "사실" and [e.n for e in result.cited] == [2]
    assert collector.calls == [("282631", CLAIM)]
    assert graph.states[0]["task"] == "factcheck" and graph.states[0]["question"] == CLAIM


def test_tc_f2010_03_no_citation_downgraded(catalog):
    answer = json.dumps({"verdict": "사실", "reason": "그렇다", "citations": []})
    result, *_ = _check(catalog, answer)
    assert result.verdict == "확인 불가" and result.cited == []


@pytest.mark.parametrize(
    "answer",
    [json.dumps({"verdict": "아마도", "reason": "[근거 2]", "citations": [2]}), "판정 불가 {깨짐"],
)
def test_tc_f2010_04_unknown_label_or_broken(catalog, answer):
    result, *_ = _check(catalog, answer)
    assert result.verdict == "확인 불가"


def test_tc_f2010_04_broken_json_reason(catalog):
    result, *_ = _check(catalog, "판정 불가 {깨짐")
    assert result.reason == "판정 결과를 해석하지 못했습니다."


def test_tc_f2010_05_out_of_range_citations(catalog):
    answer = json.dumps({"verdict": "거짓", "reason": "[합성] 다르다", "citations": [9]})
    result, *_ = _check(catalog, answer)  # 근거 4개
    assert result.verdict == "확인 불가" and result.cited == []


def test_tc_f2010_02_reason_citations_merged(catalog):
    answer = json.dumps({"verdict": "거짓", "reason": "[합성] 13척이다 [근거 3]", "citations": []})
    result, *_ = _check(catalog, answer)
    assert result.verdict == "거짓" and [e.n for e in result.cited] == [3]
