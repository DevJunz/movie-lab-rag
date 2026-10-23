"""SPEC-F2009 영화 선택 및 질의응답 화면 — 가짜 서비스를 넘긴 `AppTest`."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from movielab.core.types import AnswerResult, CitedResult, CollectReport, Evidence
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog


def _evidence(n: int) -> Evidence:
    return Evidence(
        n=n, chunk_id=f"c{n}", source_kind="wiki", source_type="위키백과", title=f"문서{n}",
        url=f"https://example.invalid/{n}", license="CC BY-SA 4.0", text="[합성] 본문",
    )  # fmt: skip


class FakeQA:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def ask(self, movie_id, question, on_progress=None):
        self.calls.append((movie_id, question))
        evidences = [_evidence(n) for n in (1, 2, 3)]
        answer = f"[합성] {movie_id}에 대한 답 [근거 1][근거 3]"
        cited = CitedResult(cited=[evidences[0], evidences[2]], uncited=False)
        return AnswerResult(
            answer=answer, evidences=evidences, cited=cited.cited, uncited=cited.uncited,
            not_found=False, collect=CollectReport(item_id=movie_id, question=question),
        )  # fmt: skip


class FakeServices:
    def __init__(self, movies_path, settings) -> None:
        self.catalog = Catalog(lambda: load_items(movies_path))
        self.qa = FakeQA()
        self.profile = MOVIE_PROFILE
        self.settings = settings

    def index_counts(self):
        return 12, 34


def _app(services):
    from movielab.ui.streamlit_app import main

    main(services)


@pytest.fixture
def services(movies_small_path, tmp_settings):
    return FakeServices(movies_small_path, tmp_settings)


@pytest.fixture
def at(services):
    app = AppTest.from_function(_app, args=(services,), default_timeout=10)
    app.run()
    assert not app.exception
    return app


def _select(at: AppTest, movie_id: str) -> None:
    at.sidebar.selectbox[0].select(movie_id).run()
    assert not at.exception


def _ask(at: AppTest, question: str) -> None:
    at.chat_input[0].set_value(question).run()
    assert not at.exception


def _chat_texts(at: AppTest) -> list[str]:
    return [m.value for msg in at.chat_message for m in msg.markdown]


def test_tc_f2009_01_movie_options_distinguish_same_titles(at):
    labels = at.sidebar.selectbox[0].options  # 화면에 보이는 형식
    assert len(labels) == 12
    assert "괴물 (2006)" in labels and "괴물 (1982)" in labels
    assert "미녀와 야수 (1991)" in labels and "미녀와 야수 (2017)" in labels


def test_tc_f2009_04_no_selection_disables_input(at):
    assert at.chat_input[0].proto.disabled is True
    assert any("영화를 먼저 선택하세요" in i.value for i in at.info)


def test_tc_f2009_02_question_uses_selected_movie(at, services):
    _select(at, "157336")
    assert at.chat_input[0].proto.disabled is False
    _ask(at, "블랙홀은?")
    assert services.qa.calls == [("157336", "블랙홀은?")]
    texts = _chat_texts(at)
    assert "블랙홀은?" in texts
    assert any("157336에 대한 답" in t for t in texts)


def test_tc_f2009_03_histories_kept_per_movie(at, services):
    _select(at, "157336")
    _ask(at, "인터스텔라 질문")
    _select(at, "282631")
    assert not any("인터스텔라 질문" in t for t in _chat_texts(at))
    _ask(at, "명량 질문")
    assert services.qa.calls[-1] == ("282631", "명량 질문")
    _select(at, "157336")
    texts = _chat_texts(at)
    assert any("인터스텔라 질문" in t for t in texts)
    assert not any("명량 질문" in t for t in texts)


def test_tc_f2009_07_evidence_shown_and_clear_history(at):
    _select(at, "157336")
    _ask(at, "블랙홀은?")
    text = "\n".join(m.value for m in at.markdown)
    assert "[근거 1]" in text and "[근거 3]" in text and "**[근거 2]**" not in text
    clear = next(b for b in at.sidebar.button if "대화 지우기" in b.label)
    clear.click().run()
    assert not any("블랙홀은?" in t for t in _chat_texts(at))
