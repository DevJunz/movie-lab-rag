"""진행 상태 상자의 문구 · 수집 상세 (SPEC-F2012 §3.1).

수집기 · 서비스가 보내는 단계 키를 사람이 읽는 문구로 바꾼다.
관람 가이드 · 사실 판정 · 조건 탐색도 같이 쓴다.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from movielab.core import messages
from movielab.core.domain import DomainProfile
from movielab.core.types import CollectReport


def _joined(values: Any) -> str:
    items = [str(v) for v in values or []]
    return ", ".join(items) if items else messages.NONE_MARK


def progress_line(stage: str, info: dict[str, Any], profile: DomainProfile) -> str | None:
    """단계 하나의 표시 문구. 모르는 단계는 None (표시하지 않는다)."""
    key = stage
    values: dict[str, Any] = dict(info)
    if stage == "extract_queries" and info.get("queries"):
        key, values["queries"] = "extract_queries_done", _joined(info["queries"])
    elif stage == "done":
        key = "done" if info.get("titles") else "done_none"
        values["titles"] = _joined(info.get("titles"))
        values.setdefault("rejected", 0)
    template = messages.PROGRESS.get(key)
    if template is None:
        return None
    try:
        return profile.render(template, **values)
    except (KeyError, IndexError, ValueError):
        return None


def render_collect_detail(report: CollectReport, profile: DomainProfile) -> None:
    """수집 상세 — 검색어, 색인한 문서, 버린 문서와 사유 (V4.2-1, V4.2-2)."""
    st.markdown(messages.COLLECT_DETAIL_QUERIES.format(queries=_joined(report.queries)))
    st.markdown(messages.COLLECT_DETAIL_INDEXED.format(titles=_joined(report.indexed_titles)))
    rejected = [f"{r.title} ({r.reason})" for r in report.rejected]
    st.markdown(messages.COLLECT_DETAIL_REJECTED.format(items=_joined(rejected)))
    if "SOURCE_FALLBACK" in report.notices:
        st.info(messages.render("SOURCE_FALLBACK", profile.labels()))
