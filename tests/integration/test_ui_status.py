"""SPEC-F2012 진행 상태 및 안내 — 가짜 서비스를 넘긴 `AppTest`."""

from __future__ import annotations

import dataclasses

import pytest
from streamlit.testing.v1 import AppTest

from movielab.core.types import AnswerResult, CollectReport, Evidence, Rejection
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.health import HealthStatus


def _evidence(n: int) -> Evidence:
    return Evidence(
        n=n, chunk_id=f"c{n}", source_kind="wiki", source_type="위키백과", title=f"문서{n}",
        url=f"https://example.invalid/{n}", license="CC BY-SA 4.0", text="[합성] 본문",
    )  # fmt: skip


class FakeQA:
    def __init__(self, *, no_external=False, error: Exception | None = None) -> None:
        self.no_external = no_external
        self.error = error

    def ask(self, movie_id, question, on_progress=None):
        if self.error is not None:
            raise self.error
        stages = [
            ("extract_queries", {}),
            ("extract_queries", {"queries": ["블랙홀", "웜홀"]}),
            ("search", {"query": "블랙홀", "current": 1, "total": 2}),
            ("fetch", {"title": "블랙홀", "current": 1, "total": 1}),
            ("index", {"title": "블랙홀"}),
            ("done", {"titles": ["인터스텔라", "블랙홀"], "rejected": 1}),
            ("retrieve", {}),
            ("generate", {}),
        ]
        for stage, info in stages:
            if on_progress is not None:
                on_progress(stage, info)
        report = CollectReport(
            item_id=movie_id, question=question, queries=["블랙홀", "웜홀"],
            indexed_titles=["인터스텔라", "블랙홀"],
            rejected=[Rejection("9", "블랙홀 (음반)", "p2_not_selected")],
        )  # fmt: skip
        evidences = [_evidence(1)]
        return AnswerResult(
            answer="[합성] 답 [근거 1]", evidences=evidences, cited=evidences, uncited=False,
            not_found=False, collect=report, no_external=self.no_external,
            timings={"total": 1.25},
        )  # fmt: skip


class FakeServices:
    def __init__(self, movies_path, settings, *, health, qa=None, profile=MOVIE_PROFILE):
        self.catalog = Catalog(lambda: load_items(movies_path))
        self.qa = qa or FakeQA()
        self.profile = profile
        self.settings = settings
        self._health = health

    def health(self):
        return self._health


OK = HealthStatus(api_key_ok=True, meta_count=12, docs_count=34)


def _app(services):
    from movielab.ui.streamlit_app import main

    main(services)


def _run(services) -> AppTest:
    at = AppTest.from_function(_app, args=(services,), default_timeout=10)
    at.run()
    assert not at.exception
    return at


def _ask(at: AppTest, movie_id: str = "157336", question: str = "블랙홀은?") -> AppTest:
    at.sidebar.selectbox[0].select(movie_id).run()
    at.chat_input[0].set_value(question).run()
    assert not at.exception
    return at


def _all_text(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    parts += (
        [e.value for e in at.error] + [w.value for w in at.warning] + [i.value for i in at.info]
    )
    return "\n".join(parts)


@pytest.fixture
def make(movies_small_path, tmp_settings):
    def factory(**kwargs):
        kwargs.setdefault("health", OK)
        return FakeServices(movies_small_path, tmp_settings, **kwargs)

    return factory


def test_tc_f2012_01_progress_status_and_titles(make):
    at = _ask(_run(make()))
    statuses = at.status
    assert len(statuses) == 1
    status = statuses[0]
    assert status.state == "complete" and status.label.startswith("완료 (")
    text = _all_text(at)
    assert "검색어: 블랙홀, 웜홀" in text
    assert "답변을 작성하는 중" in text
    assert "수집한 문서: 인터스텔라, 블랙홀" in text and "버린 문서 1건" in text
    assert "블랙홀 (음반)" in text and "p2_not_selected" in text  # 수집 상세


def test_tc_f2012_02_missing_key_stops(make):
    at = _run(make(health=dataclasses.replace(OK, api_key_ok=False)))
    assert any("GMS API 키가 설정되지 않았습니다" in e.value for e in at.error)
    assert len(at.chat_input) == 0
    assert "sk-" not in _all_text(at)


def test_tc_f2012_03_empty_index_disables_input(make):
    at = _run(make(health=dataclasses.replace(OK, meta_count=0, docs_count=0)))
    assert any("scripts.index_meta" in w.value for w in at.warning)
    at.sidebar.selectbox[0].select("157336").run()
    assert at.chat_input[0].proto.disabled is True


def test_tc_f2012_04_no_external_docs_notice(make):
    at = _ask(_run(make(qa=FakeQA(no_external=True))))
    assert any("관련 위키백과 문서를 찾지 못했습니다" in i.value for i in at.info)


def test_tc_f2012_05_disclaimer_shown_when_enabled(make, tmp_settings):
    from movielab.config import Settings

    raw = {**tmp_settings.raw, "domain": {"disclaimer_enabled": True}}
    profile = dataclasses.replace(MOVIE_PROFILE, disclaimer="[합성] 면책: 참고용 정보입니다.")
    services = make(profile=profile)
    services.settings = Settings(raw, tmp_settings.source, tmp_settings.secrets)
    at = _ask(_run(services))
    assert any("[합성] 면책" in c.value for c in at.caption)


def test_tc_f2012_06_no_disclaimer_by_default(make):
    at = _ask(_run(make()))
    assert not any("면책" in c.value for c in at.caption)


def test_tc_f2012_08_unexpected_error_hidden(make):
    at = _ask(_run(make(qa=FakeQA(error=RuntimeError("boom sk-test")))))
    errors = [e.value for e in at.error]
    assert errors == ["처리 중 문제가 발생했습니다. 잠시 후 다시 시도하세요."]
    text = _all_text(at)
    assert "boom" not in text and "Traceback" not in text and "sk-test" not in text
