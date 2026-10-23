"""SPEC-F2011 조건 탐색 화면 — 가짜 서비스를 넘긴 `AppTest`."""

from __future__ import annotations

import dataclasses

import pytest
from streamlit.testing.v1 import AppTest

from movielab.core.types import ExploreItem, ExploreResult
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.health import HealthStatus

OK = HealthStatus(api_key_ok=True, meta_count=12, docs_count=0)


class FakeExplore:
    def __init__(self, catalog, ids):
        self.catalog = catalog
        self.ids = ids
        self.calls: list[str] = []

    def search(self, condition, on_progress=None):
        self.calls.append(condition)
        if on_progress is not None:
            on_progress("explore_parse", {})
        items = [ExploreItem(self.catalog.get(i), f"[합성] {i} 이유") for i in self.ids]
        return ExploreResult(condition=condition, parsed={}, candidates=len(items), items=items)


class FakeServices:
    def __init__(self, movies_path, settings, *, ids=("900001",), health=OK):
        self.catalog = Catalog(lambda: load_items(movies_path))
        self.explore = FakeExplore(self.catalog, list(ids))
        self.qa = None
        self.profile = MOVIE_PROFILE
        self.settings = settings
        self._health = health

    def health(self):
        return self._health


def _app(services):
    from movielab.ui.streamlit_app import main

    main(services)


@pytest.fixture
def make(movies_small_path, tmp_settings):
    def factory(**kwargs):
        return FakeServices(movies_small_path, tmp_settings, **kwargs)

    return factory


def _open_explore(services) -> AppTest:
    at = AppTest.from_function(_app, args=(services,), default_timeout=10)
    at.run()
    at.radio(key="page").set_value("조건 탐색").run()
    assert not at.exception
    return at


def _search(at: AppTest, condition: str) -> AppTest:
    at.text_input(key="explore_condition").set_value(condition)
    next(b for b in at.button if b.label == "찾기").click().run()
    assert not at.exception
    return at


def test_tc_f2011_05_card_button_switches_to_ask(make):
    services = make()
    at = _search(_open_explore(services), "1990년대 한국 스릴러")
    assert services.explore.calls == ["1990년대 한국 스릴러"]
    text = "\n".join(m.value for m in at.markdown)
    assert "쉬리 (1999)" in text and "[합성] 900001 이유" in text
    button = next(b for b in at.button if b.label == "이 영화로 질문하기")
    button.click().run()
    assert not at.exception
    assert at.session_state["movie_id"] == "900001"
    assert at.session_state["page"] == "질문하기"
    assert at.sidebar.selectbox[0].value == "900001"


def test_tc_f2011_10_empty_result_notice(make):
    at = _search(_open_explore(make(ids=())), "없는 조건")
    assert any("조건에 맞는 영화를 찾지 못했습니다" in i.value for i in at.info)


def test_tc_f2011_10_empty_index_disables_input(make):
    at = _open_explore(make(health=dataclasses.replace(OK, meta_count=0)))
    assert at.text_input(key="explore_condition").disabled is True
