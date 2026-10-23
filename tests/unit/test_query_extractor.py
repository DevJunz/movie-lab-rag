"""SPEC-F2003 검색어 추출 (프롬프트 1)."""

from __future__ import annotations

import pytest

from movielab.collect.query_extractor import QueryExtractor, QueryPlan
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from tests.fakes import FakeChatModel

TASK = "검색어 추출"
QUESTION = "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?"
ITEM_QUERIES = ["인터스텔라 (2014년 영화)", "인터스텔라 (영화)", "인터스텔라"]


@pytest.fixture
def interstellar(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _extract(tmp_settings, item, response, question=QUESTION):
    llm = FakeChatModel(rules={TASK: response})
    plan = QueryExtractor(llm, MOVIE_PROFILE, tmp_settings).extract(item, question)
    return plan, llm


def test_tc_f2003_01_prompt_has_role_item_question_and_json_instruction(tmp_settings, interstellar):
    _, llm = _extract(tmp_settings, interstellar, '["블랙홀"]')
    (prompt,) = llm.prompts_for(TASK)
    assert prompt.startswith("[작업: 검색어 추출]")
    assert "영화 큐레이터" in prompt
    assert "인터스텔라 (2014)" in prompt and "크리스토퍼 놀란" in prompt
    assert "줄거리(앞부분):" in prompt
    assert QUESTION in prompt
    assert "JSON" in prompt and "3~5개" in prompt


def test_tc_f2003_02_item_queries_always_first(tmp_settings, interstellar):
    plan, _ = _extract(tmp_settings, interstellar, '["웜홀", "블랙홀"]')
    assert isinstance(plan, QueryPlan)
    assert plan.item_queries == ITEM_QUERIES
    assert plan.llm_queries == ["웜홀", "블랙홀"]
    assert plan.all == ITEM_QUERIES + ["웜홀", "블랙홀"]
    assert plan.fallback is False


def test_tc_f2003_03_code_fence_and_trailing_text_parsed(tmp_settings, interstellar):
    plan, _ = _extract(tmp_settings, interstellar, '```json\n["웜홀"]\n``` 참고하세요')
    assert plan.llm_queries == ["웜홀"] and not plan.fallback


def test_tc_f2003_04_unparseable_falls_back_to_item_queries(tmp_settings, interstellar):
    plan, _ = _extract(tmp_settings, interstellar, "검색어는 웜홀입니다")
    assert plan.llm_queries == [] and plan.fallback
    assert plan.all == ITEM_QUERIES


def test_tc_f2003_05_llm_error_falls_back(tmp_settings, interstellar):
    plan, _ = _extract(tmp_settings, interstellar, RuntimeError("GMS 장애"))
    assert plan.fallback and plan.all == ITEM_QUERIES


def test_tc_f2003_06_cleanup_dedupe_and_limit(tmp_settings, interstellar):
    response = '["웜홀", " 웜홀 ", "", 3, "인터스텔라", "a", "b", "c", "d", "e"]'
    plan, _ = _extract(tmp_settings, interstellar, response)
    assert plan.llm_queries == ["웜홀", "a", "b", "c", "d"]  # 최대 5개 (A-05)
    assert len(plan.all) == len(set(q.lower() for q in plan.all))


def test_tc_f2003_06_empty_array_is_fallback(tmp_settings, interstellar):
    plan, _ = _extract(tmp_settings, interstellar, "[]")
    assert plan.fallback and plan.llm_queries == []
