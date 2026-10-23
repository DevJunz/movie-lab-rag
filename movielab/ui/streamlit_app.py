"""Movie Lab 화면 (Streamlit) — 영화 선택 · 질의응답 (SPEC-F2009), 진행 상태 · 안내 (SPEC-F2012).

    streamlit run movielab/ui/streamlit_app.py

화면은 `main(services)` 하나로 그린다. 실행하면 container의 실제 서비스를,
테스트는 가짜 서비스를 넘긴다. `services`가 주는 것: `catalog`(항목 목록 · 조회),
`qa`(`ask`), `profile`, `settings`, `health()`.

메뉴는 `session_state["page"]`에 묶인 선택 위젯이다 —
다른 화면(F2011 카드 등)이 코드로 전환할 수 있게.
화면은 `PAGES`에 등록한다. 이 SPEC은 질문하기 화면만 만든다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import streamlit as st

from movielab.core import messages
from movielab.core.errors import MovieLabUserError
from movielab.core.types import CitedResult, ItemRecord
from movielab.ui.components.evidence import render_evidence
from movielab.ui.components.status import progress_line, render_collect_detail

logger = logging.getLogger(__name__)


def _histories() -> dict[str, list[dict[str, Any]]]:
    """영화별 대화 기록 — 브라우저 세션 동안만 (A-20)."""
    return st.session_state.setdefault("histories", {})


def _sidebar(services: Any, health: Any) -> ItemRecord | None:
    profile = services.profile
    st.sidebar.title(messages.APP_TITLE)
    if health.meta_count:
        st.sidebar.caption(
            profile.render(
                messages.INDEX_COUNTS,
                items=f"{health.meta_count:,}",
                chunks=f"{health.docs_count:,}",
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


def _disclaimer(services: Any) -> str | None:
    """면책 안내 — 도메인 프로필에 문구가 있고 설정으로 켰을 때만 (F2012 §3.3)."""
    if services.profile.disclaimer and services.settings.domain.disclaimer_enabled:
        return services.profile.disclaimer
    return None


def _render_message(message: dict[str, Any], services: Any) -> None:
    with st.chat_message(message["role"]):
        if message.get("error"):
            st.error(message["content"])
            return
        if message["role"] == "assistant" and message.get("no_external"):
            st.info(messages.render("NO_EXTERNAL_DOCS", services.profile.labels()))
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_evidence(
                CitedResult(cited=message["cited"], uncited=message["uncited"]),
                services.profile,
                preview_chars=services.settings.ui.evidence_preview_chars,
            )
            disclaimer = _disclaimer(services)
            if disclaimer:
                st.caption(disclaimer)


def _answer(services: Any, item: ItemRecord, question: str) -> dict[str, Any]:
    """질문 하나를 처리해 대화 기록에 넣을 답변 메시지를 만든다.

    진행 상태 상자에 단계를 띄우고, 끝나면 접어서 수집 상세를 담는다. 오류는 안내 문구로 바꾼다.
    """
    profile = services.profile
    labels = profile.labels()
    started = time.monotonic()
    with st.status(messages.STATUS_RUNNING, expanded=True) as status:

        def on_progress(stage: str, info: dict[str, Any]) -> None:
            line = progress_line(stage, info, profile)
            if line:
                status.write(line)

        try:
            result = services.qa.ask(item.item_id, question, on_progress)
        except MovieLabUserError as error:
            logger.warning("안내 오류: %s", error)
            status.update(label=messages.STATUS_FAILED, state="error", expanded=False)
            text = messages.render(error.code, labels, item_id=item.item_id)
            return {
                "role": "assistant",
                "content": text,
                "cited": [],
                "uncited": True,
                "error": True,
            }
        except Exception:
            logger.exception("질문 처리 실패")
            status.update(label=messages.STATUS_FAILED, state="error", expanded=False)
            text = messages.render("GENERIC_ERROR", labels)
            return {
                "role": "assistant",
                "content": text,
                "cited": [],
                "uncited": True,
                "error": True,
            }
        render_collect_detail(result.collect, profile)
        seconds = result.timings.get("total", time.monotonic() - started)
        status.update(
            label=messages.STATUS_DONE.format(seconds=seconds), state="complete", expanded=False
        )
    return {
        "role": "assistant",
        "content": result.answer,
        "cited": result.cited,
        "uncited": result.uncited,
        "notices": result.notices,
        "collect": result.collect,
        "no_external": result.no_external,
    }


def _page_ask(services: Any, item: ItemRecord | None, *, ready: bool = True) -> None:
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
    question = st.chat_input(
        profile.render(messages.ASK_PLACEHOLDER, item_name=item.display_name), disabled=not ready
    )
    if not question:
        return
    asked = {"role": "user", "content": question}
    history.append(asked)
    _render_message(asked, services)
    answer = _answer(services, item, question)
    history.append(answer)
    _render_message(answer, services)


# 메뉴 이름 → 화면 `(services, item, *, ready)`. 다른 화면은 그 기능의 SPEC이 더한다.
PAGES: dict[str, Callable[..., None]] = {messages.MENU_ASK: _page_ask}


def main(services: Any) -> None:
    profile = services.profile
    health = services.health()
    if not health.api_key_ok:  # 키가 없으면 안내하고 멈춘다 (F2012 §3.2)
        st.error(messages.render("API_KEY_MISSING", profile.labels()))
        st.stop()
    item = _sidebar(services, health)
    ready = health.meta_count > 0
    if not ready:  # 메타 색인이 비면 질문 · 탐색 비활성
        st.warning(messages.render("INDEX_EMPTY", profile.labels()))
    page = st.radio("menu", list(PAGES), horizontal=True, key="page", label_visibility="collapsed")
    PAGES[page](services, item, ready=ready)


@st.cache_resource
def _services() -> Any:
    """실제 서비스 — LLM · Chroma · 그래프를 프로세스에서 한 번만 만든다."""
    from movielab.config import load_settings
    from movielab.container import build_services

    return build_services(load_settings())


if __name__ == "__main__":
    st.set_page_config(page_title=messages.APP_TITLE, layout="wide")
    main(_services())
