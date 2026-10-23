"""조립 지점(composition root). 구체 구현을 연결하는 유일한 곳이다 (SPEC-NF2005 §3.6).

UI · API · 스크립트 · 테스트는 모두 `build_services`로 서비스를 얻는다.
인자로 준 의존성은 그대로 쓰고, 주지 않은 LLM · 임베딩은 처음 쓸 때 GMS로 만든다(SPEC-NF2003).
키가 없어도 생성은 성공한다 — 앱이 시작되어 키 안내 화면을 띄울 수 있어야 하기 때문이다.
"""

from __future__ import annotations

from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from movielab import providers
from movielab.config import Settings
from movielab.core.domain import DomainProfile
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.index.store import VectorStore
from movielab.services.catalog import Catalog


class Services:
    def __init__(
        self,
        settings: Settings,
        profile: DomainProfile,
        *,
        llm: Any = None,
        embeddings: Any = None,
        http: Any = None,
    ) -> None:
        self.settings = settings
        self.profile = profile
        self.http = http  # 실제 HTTP 세션은 SPEC-NF2006에서 만든다
        self._llm = llm
        self._embeddings = embeddings
        self.catalog = Catalog(lambda: self._load_items())
        self._store: VectorStore | None = None

    def _load_items(self) -> Any:
        if self.profile.load_items is None:
            raise ValueError("DomainProfile.load_items가 없다")
        return self.profile.load_items(self.settings)

    @property
    def llm(self) -> Any:
        if self._llm is None:
            self._llm = providers.make_chat_model(self.settings)
        return self._llm

    @property
    def embeddings(self) -> Any:
        if self._embeddings is None:
            self._embeddings = providers.make_embeddings(self.settings)
        return self._embeddings

    @property
    def store(self) -> VectorStore:
        """Chroma 저장소. 임베딩은 처음 색인 · 검색할 때 만든다 (건수 조회는 키 없이 가능)."""
        if self._store is None:
            client = chromadb.PersistentClient(
                path=str(self.settings.path("chroma_dir")),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._store = VectorStore(client, lambda: self.embeddings, self.settings)
        return self._store


def build_services(
    settings: Settings,
    *,
    llm: Any = None,
    embeddings: Any = None,
    http: Any = None,
    profile: DomainProfile | None = None,
) -> Services:
    return Services(settings, profile or MOVIE_PROFILE, llm=llm, embeddings=embeddings, http=http)
