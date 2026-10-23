"""SPEC-F2004 프롬프트 2 — 후보 선별."""

from __future__ import annotations

import pytest

from movielab.collect.selector import CandidateSelector
from movielab.core.types import Candidate
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from tests.fakes import FakeChatModel

TASK = "후보 선별"
QUESTION = "블랙홀 묘사는 실제 물리와 얼마나 다른가?"
BODY_MARK = "본문에만 있는 문장"


@pytest.fixture
def item(movies_small_path):
    return next(i for i in load_items(movies_small_path).items if i.item_id == "157336")


def _candidates():
    return [
        Candidate(page_id="2", title="블랙홀", snippet="빛도 빠져나올 수 없는 천체"),
        Candidate(page_id="3", title="블랙홀 (음반)", snippet="가수의 음반"),
        Candidate(page_id="4", title="웜홀", snippet="시공간의 통로"),
    ]


def _select(tmp_settings, item, response):
    llm = FakeChatModel(rules={TASK: response})
    result = CandidateSelector(llm, MOVIE_PROFILE, tmp_settings).select(
        item, QUESTION, _candidates()
    )
    return result, llm


def test_tc_f2004_02_prompt_shows_titles_and_snippets_only(tmp_settings, item):
    _, llm = _select(tmp_settings, item, "[0]")
    (prompt,) = llm.prompts_for(TASK)
    assert prompt.startswith("[작업: 후보 선별]")
    assert "인터스텔라 (2014)" in prompt and QUESTION in prompt
    assert "0. 블랙홀: 빛도 빠져나올 수 없는 천체" in prompt
    assert "2. 웜홀: 시공간의 통로" in prompt
    assert BODY_MARK not in prompt
    assert "JSON 정수 배열" in prompt and "최대 5개" in prompt


def test_tc_f2004_03_selected_and_rejected(tmp_settings, item):
    result, _ = _select(tmp_settings, item, "[2, 0]")
    assert [c.title for c in result.selected] == ["웜홀", "블랙홀"]
    assert [(r.title, r.reason) for r in result.rejected] == [("블랙홀 (음반)", "p2_not_selected")]


def test_tc_f2004_07_invalid_numbers_ignored(tmp_settings, item):
    result, _ = _select(tmp_settings, item, '["1", 7, -1, 1, "x", true, 1]')
    assert [c.page_id for c in result.selected] == ["3"]


def test_tc_f2004_07_broken_output_selects_nothing(tmp_settings, item):
    result, _ = _select(tmp_settings, item, "고를 문서가 없습니다")
    assert result.selected == [] and len(result.rejected) == 3


def test_tc_f2004_07_llm_error_selects_nothing(tmp_settings, item):
    result, _ = _select(tmp_settings, item, RuntimeError("GMS 장애"))
    assert result.selected == []


def test_tc_f2004_03_limit_applied(tmp_settings, item):
    tmp_settings.raw["collect"]["max_selected_docs"] = 2
    result, _ = _select(tmp_settings, item, "[0, 1, 2]")
    assert len(result.selected) == 2
    assert result.rejected[-1].reason == "over_limit"


def test_tc_f2004_01_empty_candidates_no_llm_call(tmp_settings, item):
    llm = FakeChatModel(rules={TASK: "[0]"})
    result = CandidateSelector(llm, MOVIE_PROFILE, tmp_settings).select(item, QUESTION, [])
    assert result.selected == [] and llm.calls == []
