"""조립 지점(composition root). 구체 구현을 연결하는 유일한 곳이다 (SPEC-NF2005 §3.6).

UI · API · 스크립트 · 테스트는 모두 `build_services`로 서비스를 얻는다.
인자로 준 의존성은 그대로 쓰고, 주지 않은 것은 실제 구현으로 만든다.
(실제 GMS 연결은 SPEC-NF2003에서 더한다.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from movielab.config import Settings
from movielab.core.domain import DomainProfile
from movielab.data.domain_movie import MOVIE_PROFILE


@dataclass
class Services:
    settings: Settings
    profile: DomainProfile
    llm: Any = None
    embeddings: Any = None
    http: Any = None


def build_services(
    settings: Settings,
    *,
    llm: Any = None,
    embeddings: Any = None,
    http: Any = None,
    profile: DomainProfile | None = None,
) -> Services:
    return Services(
        settings=settings,
        profile=profile or MOVIE_PROFILE,
        llm=llm,
        embeddings=embeddings,
        http=http,
    )
