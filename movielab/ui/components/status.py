"""진행 상태 상자의 문구 · 수집 상세 (SPEC-F2012 §3.1).

수집기 · 서비스가 보내는 단계 키를 사람이 읽는 문구로 바꾼다.
관람 가이드 · 사실 판정 · 조건 탐색도 같이 쓴다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st

from movielab.core import messages
from movielab.core.domain import DomainProfile
from movielab.core.errors import MovieLabUserError
from movielab.core.types import CollectReport

logger = logging.getLogger(__name__)

T = TypeVar("T")
Progress = Callable[[str, dict[str, Any]], None]


def _joined(values: Any) -> str:
    items = [str(v) for v in values or []]
    return ", ".join(items) if items else messages.NONE_MARK


def progress_line(stage: str, info: dict[str, Any], profile: DomainProfile) -> str | None:
    """단계 하나의 표시 문구. 모르는 단계는 None (표시하지 않는다). 웹 API와 같은 함수."""
    return messages.progress_text(stage, info, profile)


def render_collect_detail(report: CollectReport, profile: DomainProfile) -> None:
    """수집 상세 — 검색어, 색인한 문서, 버린 문서와 사유 (V4.2-1, V4.2-2)."""
    st.markdown(messages.COLLECT_DETAIL_QUERIES.format(queries=_joined(report.queries)))
    st.markdown(messages.COLLECT_DETAIL_INDEXED.format(titles=_joined(report.indexed_titles)))
    rejected = [f"{r.title} ({r.reason})" for r in report.rejected]
    st.markdown(messages.COLLECT_DETAIL_REJECTED.format(items=_joined(rejected)))
    if "SOURCE_FALLBACK" in report.notices:
        st.info(messages.render("SOURCE_FALLBACK", profile.labels()))


def run_with_status(profile: DomainProfile, action: Callable[[Progress], T]) -> T | None:
    """진행 상태 상자를 띄우고 `action(on_progress)`를 실행한다 (F2012 · NF2004).

    끝나면 상자를 접고 소요 시간을 보인다. 안내 오류는 그 문구로, 그 밖의 예외는
    `GENERIC_ERROR`로 보이고 None을 돌려준다(예외 메시지 · traceback은 로그에만).
    """
    started = time.monotonic()
    with st.status(messages.STATUS_RUNNING, expanded=True) as status:

        def on_progress(stage: str, info: dict[str, Any]) -> None:
            line = progress_line(stage, info, profile)
            if line:
                status.write(line)

        try:
            result = action(on_progress)
        except MovieLabUserError as error:
            logger.warning("안내 오류: %s", error)
            status.update(label=messages.STATUS_FAILED, state="error", expanded=False)
            st.error(messages.render(error.code, profile.labels()))
            return None
        except Exception:
            logger.exception("처리 실패")
            status.update(label=messages.STATUS_FAILED, state="error", expanded=False)
            st.error(messages.render("GENERIC_ERROR", profile.labels()))
            return None
        seconds = time.monotonic() - started
        status.update(
            label=messages.STATUS_DONE.format(seconds=seconds), state="complete", expanded=False
        )
    return result
