"""Movie Lab 화면 (Streamlit) — 영화 선택 · 질의응답 (SPEC-F2009).

    streamlit run movielab/ui/streamlit_app.py

화면은 `main(services)` 하나로 그린다. 실행하면 container의 실제 서비스를,
테스트는 가짜 서비스를 넘긴다. `services`가 주는 것: `catalog`(항목 목록 · 조회),
`qa`(`ask`), `profile`, `settings`, `index_counts()`.

메뉴는 `session_state["page"]`에 묶인 선택 위젯이다 —
다른 화면(F2011 카드 등)이 코드로 전환할 수 있게.
화면은 `PAGES`에 등록한다. 이 SPEC은 질문하기 화면만 만든다.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import streamlit as st

from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.core.types import CitedResult, ItemRecord
from movielab.ui.components.evidence import render_evidence

logger = logging.getLogger(__name__)


def _histories() -> dict[str, list[dict[str, Any]]]:
    """영화별 대화 기록 — 브라우저 세션 동안만 (A-20)."""
    return st.session_state.setdefault("histories", {})


def _sidebar(services: Any) -> ItemRecord | None:
    profile = services.profile
    st.sidebar.title(messages.APP_TITLE)
    counts = services.index_counts()
    if counts is not None:
        items_count, chunks_count = counts
        st.sidebar.caption(
            profile.render(
                messages.INDEX_COUNTS, items=f"{items_count:,}", chunks=f"{chunks_count:,}"
            )
        )
    by_id = {item.item_id: item for item in services.catalog.items()}
    movie_id = st.sidebar.selectbox(
        profile.render(messages.SELECT_ITEM_LABEL),
        options=list(by_id),
        index=None,
        format_func=lambda item_id: by_id[item_id].display_name,
        key="movie_id",
    )
    item = by_id.get(movie_id) if movie_id is not None else None
    if item is not None:
        st.sidebar.markdown(f"**{item.display_name}**")
        if profile.item_caption is not None:
            st.sidebar.caption(profile.item_caption(item))
        if item.url:
            st.sidebar.markdown(f"[{profile.meta_link_label} ↗]({item.url})")
        if st.sidebar.button(profile.render(messages.CLEAR_HISTORY)):
            _histories().pop(item.item_id, None)
    st.sidebar.divider()
    st.sidebar.caption(profile.attribution_notice)
    return item


def _render_message(message: dict[str, Any], services: Any) -> None:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_evidence(
                CitedResult(cited=message["cited"], uncited=message["uncited"]),
                services.profile,
                preview_chars=services.settings.ui.evidence_preview_chars,
            )


def _answer(services: Any, item: ItemRecord, question: str) -> dict[str, Any]:
    """질문 하나를 처리해 대화 기록에 넣을 답변 메시지를 만든다. 오류는 안내 문구로 바꾼다."""
    labels = services.profile.labels()
    try:
        with st.spinner(messages.ANSWERING):
            result = services.qa.ask(item.item_id, question)
    except MovieLabUserError as error:
        logger.warning("안내 오류: %s", error)
        text = messages.render(error.code, labels, item_id=item.item_id)
        return {"role": "assistant", "content": text, "cited": [], "uncited": True, "error": True}
    except Exception:
        logger.exception("질문 처리 실패")
        text = messages.render("GENERIC_ERROR", labels)
        return {"role": "assistant", "content": text, "cited": [], "uncited": True, "error": True}
    return {
        "role": "assistant",
        "content": result.answer,
        "cited": result.cited,
        "uncited": result.uncited,
        "notices": result.notices,
        "collect": result.collect,
    }


def _page_ask(services: Any, item: ItemRecord | None) -> None:
    profile = services.profile
    if item is None:
        st.info(profile.render(messages.SELECT_ITEM_FIRST))
        st.chat_input(disabled=True)
        return
    st.subheader(item.display_name)
    if profile.item_caption is not None:
        st.caption(profile.item_caption(item))
    history = _histories().setdefault(item.item_id, [])
    for message in history:
        _render_message(message, services)
    question = st.chat_input(profile.render(messages.ASK_PLACEHOLDER, item_name=item.display_name))
    if not question:
        return
    asked = {"role": "user", "content": question}
    history.append(asked)
    _render_message(asked, services)
    answer = _answer(services, item, question)
    history.append(answer)
    if answer.get("error"):
        with st.chat_message("assistant"):
            st.error(answer["content"])
        return
    _render_message(answer, services)


# 메뉴 이름 → 화면. 다른 화면은 그 기능의 SPEC이 더한다.
PAGES: dict[str, Callable[[Any, ItemRecord | None], None]] = {messages.MENU_ASK: _page_ask}


def main(services: Any) -> None:
    item = _sidebar(services)
    page = st.radio("menu", list(PAGES), horizontal=True, key="page", label_visibility="collapsed")
    PAGES[page](services, item)


@st.cache_resource
def _services() -> Any:
    """실제 서비스 — LLM · Chroma · 그래프를 프로세스에서 한 번만 만든다."""
    from movielab.config import load_settings
    from movielab.container import build_services

    return build_services(load_settings())


if __name__ == "__main__":
    st.set_page_config(page_title=messages.APP_TITLE, layout="wide")
    main(_services())
