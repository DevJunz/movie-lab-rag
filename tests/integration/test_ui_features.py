"""SPEC-F2010 관람 가이드 · 사실 판정 화면 — 가짜 서비스를 넘긴 `AppTest`."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from movielab.core.types import CollectReport, FactCheckResult, GuideResult
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.health import HealthStatus
from tests.fakes.pipeline import make_evidence


class FakeGuide:
    def generate(self, movie_id, on_progress=None):
        evidences = [make_evidence(1, meta=True), make_evidence(2), make_evidence(3)]
        return GuideResult(
            markdown="## 한 줄 소개\n[합성] 가이드 본문 [근거 2]",
            evidences=evidences, cited=[evidences[1]], uncited=False,
            collect=CollectReport(item_id=movie_id, question="가이드"),
        )  # fmt: skip


class FakeFactCheck:
    def check(self, movie_id, claim, on_progress=None):
        evidences = [make_evidence(1, meta=True), make_evidence(2), make_evidence(3)]
        return FactCheckResult(
            claim=claim, verdict="거짓", reason="[합성] 13척이다 [근거 3]",
            evidences=evidences, cited=[evidences[2]],
            collect=CollectReport(item_id=movie_id, question=claim),
        )  # fmt: skip


class FakeServices:
    def __init__(self, movies_path, settings):
        self.catalog = Catalog(lambda: load_items(movies_path))
        self.guide = FakeGuide()
        self.factcheck = FakeFactCheck()
        self.profile = MOVIE_PROFILE
        self.settings = settings

    def health(self):
        return HealthStatus(api_key_ok=True, meta_count=12, docs_count=3)


def _app(services):
    from movielab.ui.streamlit_app import main

    main(services)


@pytest.fixture
def at(movies_small_path, tmp_settings):
    app = AppTest.from_function(_app, args=(FakeServices(movies_small_path, tmp_settings),))
    app.default_timeout = 10
    app.run()
    return app


def _texts(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_tc_f2010_07_factcheck_screen(at):
    at.sidebar.selectbox[0].select("282631").run()
    at.radio(key="page").set_value("사실 판정").run()
    at.text_input(key="factcheck_claim").set_value("조선 수군의 배는 12척이었다")
    next(b for b in at.button if b.label == "판정하기").click().run()
    assert not at.exception
    text = _texts(at)
    assert "거짓" in text and "13척이다 [근거 3]" in text
    assert "**[근거 3]**" in text and "**[근거 2]**" not in text  # 인용된 근거만


def test_tc_f2010_08_guide_screen(at):
    at.sidebar.selectbox[0].select("157336").run()
    at.radio(key="page").set_value("관람 가이드").run()
    next(b for b in at.button if b.label == "가이드 만들기").click().run()
    assert not at.exception
    text = _texts(at)
    assert "가이드 본문 [근거 2]" in text and "**[근거 2]**" in text


def test_tc_f2010_12_requires_movie(at):
    at.radio(key="page").set_value("관람 가이드").run()
    assert next(b for b in at.button if b.label == "가이드 만들기").disabled is True
    assert any("영화를 먼저 선택하세요" in i.value for i in at.info)
