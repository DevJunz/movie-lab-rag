"""SPEC-NF2004 §2.2 — safe_run: 안내 오류는 문구로, 그 밖은 GENERIC_ERROR + 로그에 traceback."""

from __future__ import annotations

import logging

import pytest
from streamlit.runtime.scriptrunner_utils.exceptions import StopException

from movielab.core.errors import IndexEmptyError
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.ui.streamlit_app import safe_run


def test_tc_nf2004_04_unexpected_error_logged_with_traceback(caplog, monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr("movielab.ui.streamlit_app.st.error", shown.append)

    @safe_run(MOVIE_PROFILE)
    def action():
        raise ValueError("C:\\secret\\path")

    with caplog.at_level(logging.ERROR):
        action()
    assert shown == ["처리 중 문제가 발생했습니다. 잠시 후 다시 시도하세요."]
    records = [r for r in caplog.records if r.exc_info]
    assert records and records[0].exc_info[0] is ValueError  # traceback은 로그에만


def test_tc_nf2004_04_user_error_shows_its_notice(monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr("movielab.ui.streamlit_app.st.error", shown.append)

    @safe_run(MOVIE_PROFILE)
    def action():
        raise IndexEmptyError("빈 색인")

    action()
    assert len(shown) == 1 and "scripts.index_meta" in shown[0]


def test_tc_nf2004_04_streamlit_control_flow_passes_through():
    @safe_run(MOVIE_PROFILE)
    def action():
        raise StopException()

    with pytest.raises(StopException):
        action()
