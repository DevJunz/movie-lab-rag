"""SPEC-NF2004 내부 정보 비노출 — 가짜 서비스로 화면을 그려 키 · traceback · 프롬프트를 찾는다."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from movielab.config import Secrets, Settings
from movielab.core.types import AnswerResult, CollectReport, Evidence
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.health import HealthStatus

FAKE_KEY = "sk-test-abcdef1234567890"
GENERIC = "처리 중 문제가 발생했습니다. 잠시 후 다시 시도하세요."


class FakeQA:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def ask(self, movie_id, question, on_progress=None):
        if self.error is not None:
            raise self.error
        evidence = Evidence(
            n=1, chunk_id="c1", source_kind="wiki", source_type="위키백과", title="문서1",
            url="https://example.invalid/1", license="CC BY-SA 4.0", text="[합성] 본문",
        )  # fmt: skip
        return AnswerResult(
            answer="[합성] 답 [근거 1]", evidences=[evidence], cited=[evidence], uncited=False,
            not_found=False, collect=CollectReport(item_id=movie_id, question=question),
        )  # fmt: skip


class BrokenCatalog:
    def items(self):
        raise RuntimeError("boom C:\\secret\\movies.json")

    def get(self, item_id):
        return None


class FakeServices:
    def __init__(self, movies_path, settings, *, qa=None, catalog=None) -> None:
        self.catalog = catalog or Catalog(lambda: load_items(movies_path))
        self.qa = qa or FakeQA()
        self.profile = MOVIE_PROFILE
        self.settings = settings

    def health(self):
        return HealthStatus(api_key_ok=True, meta_count=12, docs_count=34)


def _app(services):
    from movielab.ui.streamlit_app import main

    main(services)


def _screen_text(at: AppTest) -> str:
    """화면에 보이는 모든 글자 (본문 · 사이드바 · 상태 상자 · 안내)."""
    kinds = ("title", "subheader", "markdown", "caption", "info", "warning", "error", "text")
    parts = [str(getattr(e, "value", "")) for kind in kinds for e in getattr(at, kind)]
    parts += [s.label for s in at.status]
    parts += [str(x.value) for x in at.exception]
    return "\n".join(parts)


@pytest.fixture
def keyed_settings(tmp_settings):
    return Settings(
        tmp_settings.raw, tmp_settings.source, Secrets(FAKE_KEY, "https://gms.example.invalid")
    )


def _run(services, question: str | None = "블랙홀은?") -> AppTest:
    at = AppTest.from_function(_app, args=(services,), default_timeout=10)
    at.run()
    if question is not None:
        at.sidebar.selectbox[0].select("157336").run()
        at.chat_input[0].set_value(question).run()
    return at


def test_tc_nf2004_01_service_exception_hidden(movies_small_path, keyed_settings):
    qa = FakeQA(error=ValueError("C:\\secret\\path sk-test-123"))
    at = _run(FakeServices(movies_small_path, keyed_settings, qa=qa))
    text = _screen_text(at)
    assert GENERIC in text
    for leaked in ("Traceback", "ValueError", "secret", "sk-test"):
        assert leaked not in text


def test_tc_nf2004_02_key_never_on_screen(movies_small_path, keyed_settings):
    at = _run(FakeServices(movies_small_path, keyed_settings))
    text = _screen_text(at)
    assert FAKE_KEY not in text and FAKE_KEY[:10] not in text
    assert "gms.example.invalid" not in text


def test_tc_nf2004_03_prompt_not_on_screen(movies_small_path, keyed_settings):
    at = _run(FakeServices(movies_small_path, keyed_settings))
    text = _screen_text(at)
    assert "[작업:" not in text and "규칙:" not in text


def test_tc_nf2004_08_unexpected_error_outside_question_hidden(movies_small_path, keyed_settings):
    services = FakeServices(movies_small_path, keyed_settings, catalog=BrokenCatalog())
    at = _run(services, question=None)
    text = _screen_text(at)
    assert [e.value for e in at.error] == [GENERIC]
    assert "boom" not in text and "secret" not in text and not at.exception
