"""조건 탐색 화면 (SPEC-F2011) — 조건 입력 → 진행 상태 → 결과 카드 → 질문하기로 전환."""

from __future__ import annotations

from typing import Any

import streamlit as st

from movielab.core import messages
from movielab.core.types import ExploreResult, ItemRecord
from movielab.ui.components.status import run_with_status


def _choose(item_id: str) -> None:
    """카드 버튼 콜백 — 위젯을 그리기 전에 사이드바 선택 · 메뉴를 바꾼다 (F2011 §3.3)."""
    st.session_state["movie_id"] = item_id
    st.session_state["page"] = messages.MENU_ASK


def _search(services: Any, condition: str) -> ExploreResult | None:
    return run_with_status(
        services.profile, lambda on_progress: services.explore.search(condition, on_progress)
    )


def _cards(services: Any, result: ExploreResult) -> None:
    profile = services.profile
    if not result.items:
        st.info(messages.render("EXPLORE_EMPTY", profile.labels()))
        return
    st.caption(
        messages.EXPLORE_SUMMARY.format(candidates=result.candidates, count=len(result.items))
    )
    for entry in result.items:
        item = entry.item
        with st.container(border=True):
            st.markdown(f"**{item.display_name}**")
            if profile.item_caption is not None:
                st.caption(profile.item_caption(item))
            st.markdown(messages.EXPLORE_REASON.format(reason=entry.reason))
            if item.url:
                st.markdown(
                    f"{profile.meta_source_label} · [{profile.meta_link_label} ↗]({item.url})"
                )
            st.button(
                profile.render(messages.EXPLORE_ASK_BUTTON),
                key=f"explore_pick_{item.item_id}",
                on_click=_choose,
                args=(item.item_id,),
            )


def page_explore(services: Any, item: ItemRecord | None, *, ready: bool = True) -> None:
    del item  # 탐색은 선택한 항목과 무관하다
    profile = services.profile
    condition = st.text_input(
        profile.render(messages.EXPLORE_INPUT_LABEL),
        placeholder=profile.render(messages.EXPLORE_PLACEHOLDER),
        key="explore_condition",
        disabled=not ready,
    )
    if st.button(messages.EXPLORE_BUTTON, disabled=not ready) and condition.strip():
        result = _search(services, condition.strip())
        if result is not None:
            st.session_state["explore_result"] = result
    result = st.session_state.get("explore_result")
    if result is not None:
        _cards(services, result)
