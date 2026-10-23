"""근거 목록 컴포넌트 — 답변에 실제로 인용된 근거만 보여 준다 (SPEC-F2008 §3.3).

    근거
    [근거 1] 영화 메타데이터 · 인터스텔라 (2014) · TMDB ↗
    [근거 3] 위키백과 · 블랙홀 · 원문 ↗ · CC BY-SA 4.0

화면 배치 · 서비스 연결은 질의응답 화면(F2009)이 한다. 관람 가이드 · 사실 판정(F2010)도 같이 쓴다.
"""

from __future__ import annotations

import re
from urllib.parse import quote

import streamlit as st

from movielab.core import messages
from movielab.core.domain import DomainProfile
from movielab.core.types import CitedResult, Evidence


def _link_label(evidence: Evidence, profile: DomainProfile) -> str:
    return (
        profile.meta_link_label if evidence.source_kind == "meta" else messages.EVIDENCE_SOURCE_LINK
    )


def evidence_line(evidence: Evidence, profile: DomainProfile) -> str:
    """`[근거 n] 출처 유형 · 제목 · 링크 ↗ (· 라이선스)` 한 줄 (마크다운)."""
    parts = [f"**[근거 {evidence.n}]** {evidence.source_type}", _escape(evidence.title)]
    if evidence.url:
        # 마크다운 링크가 괄호 · 공백 · 꺾쇠에서 끊기지 않게 인코딩한다
        url = quote(evidence.url, safe=":/?#=&%@+,;!$'*~.-_")
        url = url.replace("(", "%28").replace(")", "%29")
        parts.append(f"[{_link_label(evidence, profile)} ↗]({url})")
    if evidence.license:
        parts.append(evidence.license)
    return " · ".join(parts)


def _escape(text: str) -> str:
    """제목의 마크다운 특수 문자를 이스케이프한다."""
    return re.sub(r"([\\`*_\[\]<>#|~])", r"\\\1", text)


def _preview(text: str, limit: int) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[:limit] + "…"


def render_evidence(result: CitedResult, profile: DomainProfile, *, preview_chars: int) -> None:
    """인용된 근거 목록, 인용이 없으면 안내 한 줄."""
    if result.uncited:
        st.info(messages.UNCITED)
        return
    st.markdown(f"**{messages.EVIDENCE_HEADER}**")
    for evidence in result.cited:
        st.markdown(evidence_line(evidence, profile))
        with st.expander(f"[근거 {evidence.n}] 본문 미리보기"):
            st.text(_preview(evidence.text, preview_chars))  # 일반 텍스트 ($ · # 해석 안 함)
