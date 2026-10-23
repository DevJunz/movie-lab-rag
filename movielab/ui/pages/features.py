"""영화 특화 기능 화면 (SPEC-F2010) — 관람 가이드 · 사실 판정.

결과는 영화별로 마지막 것을 `session_state`에 보관해 영화를 바꿔도 섞이지 않는다.
근거 목록은 F2008 컴포넌트, 진행 상태 · 오류 안내는 F2012 공용 도우미를 쓴다.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from movielab.core import messages
from movielab.core.types import CitedResult, ItemRecord
from movielab.ui.components.evidence import render_evidence
from movielab.ui.components.status import run_with_status

# 판정 라벨 → 배지 색 (Streamlit 마크다운 색 표기)
_BADGE_COLOR = {
    messages.VERDICT_TRUE: "green",
    messages.VERDICT_FALSE: "red",
    messages.VERDICT_UNKNOWN: "gray",
}


def _results(key: str) -> dict[str, Any]:
    return st.session_state.setdefault(key, {})


def _evidence(services: Any, cited: list[Any]) -> None:
    render_evidence(
        CitedResult(cited=cited, uncited=not cited),
        services.profile,
        preview_chars=services.settings.ui.evidence_preview_chars,
    )


def _requires_item(services: Any, item: ItemRecord | None) -> None:
    if item is None:
        st.info(services.profile.render(messages.SELECT_ITEM_FIRST))


def page_guide(services: Any, item: ItemRecord | None, *, ready: bool = True) -> None:
    _requires_item(services, item)
    clicked = st.button(messages.GUIDE_BUTTON, disabled=item is None or not ready)
    if item is None:
        return
    st.subheader(item.display_name)
    results = _results("guide_results")
    if clicked:
        result = run_with_status(
            services.profile,
            lambda on_progress: services.guide.generate(item.item_id, on_progress),
        )
        if result is not None:
            results[item.item_id] = result
    result = results.get(item.item_id)
    if result is None:
        return
    st.markdown(result.markdown)
    _evidence(services, result.cited)


def page_factcheck(services: Any, item: ItemRecord | None, *, ready: bool = True) -> None:
    profile = services.profile
    _requires_item(services, item)
    claim = st.text_input(
        messages.FACTCHECK_INPUT_LABEL,
        placeholder=messages.FACTCHECK_PLACEHOLDER,
        key="factcheck_claim",
        disabled=item is None or not ready,
    )
    clicked = st.button(messages.FACTCHECK_BUTTON, disabled=item is None or not ready)
    if item is None:
        return
    st.subheader(item.display_name)
    results = _results("factcheck_results")
    if clicked and claim.strip():
        result = run_with_status(
            profile,
            lambda on_progress: services.factcheck.check(item.item_id, claim.strip(), on_progress),
        )
        if result is not None:
            results[item.item_id] = result
    result = results.get(item.item_id)
    if result is None:
        return
    color = _BADGE_COLOR.get(result.verdict, "gray")
    st.markdown(messages.FACTCHECK_CLAIM.format(claim=result.claim))
    st.markdown(f":{color}-background[**{result.verdict}**]")
    st.markdown(result.reason)
    _evidence(services, result.cited)
