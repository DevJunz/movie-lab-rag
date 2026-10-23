"""SPEC-F2011 조건 기반 탐색 — 합성 12편 색인 + 가짜 LLM."""

from __future__ import annotations

import json

import pytest

from movielab.container import build_services
from movielab.services.indexing import index_catalog
from tests.fakes import FakeChatModel, FakeClock, FakeEmbeddings

NINETIES_KO = json.dumps(
    {"semantic_query": "스릴러", "year_min": 1990, "year_max": 1999, "korean_only": True}
)


def _services(tmp_settings, rules):
    services = build_services(
        tmp_settings, llm=FakeChatModel(rules=rules), embeddings=FakeEmbeddings()
    )
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    return services


def _pick(*ids):
    return json.dumps([{"movie_id": i, "reason": f"[합성] {i} 이유"} for i in ids])


def test_tc_f2011_01_ids_outside_candidates_dropped(tmp_settings):
    rules = {"조건 해석": NINETIES_KO, "조건 선별": _pick("900001", "없는영화", "900001")}
    result = _services(tmp_settings, rules).explore.search("1990년대 한국 스릴러")
    assert [i.item.item_id for i in result.items] == ["900001"]  # 후보 밖 · 중복 제외
    assert result.items[0].reason == "[합성] 900001 이유"


def test_tc_f2011_02_structured_filter_enforced(tmp_settings):
    # E2가 2019년 한국 영화 · 1991년 해외 영화까지 골라도 코드가 걸러 낸다
    rules = {"조건 해석": NINETIES_KO, "조건 선별": _pick("496243", "10020", "900001")}
    services = _services(tmp_settings, rules)
    result = services.explore.search("1990년대 한국 스릴러")
    assert [i.item.item_id for i in result.items] == ["900001"]
    for entry in result.items:
        meta = entry.item.metadata
        assert 1990 <= meta["year"] <= 1999 and meta["original_language"] == "ko"
    selection_prompt = services.llm.prompts_for("조건 선별")[0]
    assert "id=900001" in selection_prompt and "id=496243" not in selection_prompt  # 후보부터 필터


@pytest.mark.parametrize(
    ("parse", "select"),
    [("JSON 아님", _pick("900001")), (NINETIES_KO, "고를 수 없음"), ("[1, 2]", "{}")],
)
def test_tc_f2011_03_broken_outputs_handled(tmp_settings, parse, select):
    result = _services(tmp_settings, {"조건 해석": parse, "조건 선별": select}).explore.search(
        "아무 조건"
    )
    assert isinstance(result.items, list)  # 예외 없음


def test_tc_f2011_03_broken_parse_falls_back_to_condition(tmp_settings):
    services = _services(tmp_settings, {"조건 해석": "JSON 아님", "조건 선별": "[]"})
    result = services.explore.search("우주 가족 영화")
    assert result.parsed == {"semantic_query": "우주 가족 영화"}
    assert result.candidates == 12  # 필터 없이 전체에서 후보 (합성 12편 < 20)


def test_tc_f2011_04_nothing_selected(tmp_settings):
    result = _services(tmp_settings, {"조건 해석": NINETIES_KO, "조건 선별": "[]"}).explore.search(
        "1990년대 한국 스릴러"
    )
    assert result.items == []


def test_tc_f2011_progress_stages(tmp_settings):
    stages = []
    services = _services(tmp_settings, {"조건 해석": NINETIES_KO, "조건 선별": _pick("900001")})
    services.explore.search("조건", on_progress=lambda stage, info: stages.append(stage))
    assert stages == ["explore_parse", "explore_search", "explore_select"]
