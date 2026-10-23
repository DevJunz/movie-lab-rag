"""조립 지점(composition root). 구체 구현을 연결하는 유일한 곳이다 (SPEC-NF2005 §3.6).

UI · API · 스크립트 · 테스트는 모두 `build_services`로 서비스를 얻는다.
인자로 준 의존성은 그대로 쓰고, 주지 않은 LLM · 임베딩은 처음 쓸 때 GMS로 만든다(SPEC-NF2003).
키가 없어도 생성은 성공한다 — 앱이 시작되어 키 안내 화면을 띄울 수 있어야 하기 때문이다.
"""

from __future__ import annotations

import threading
from typing import Any

import chromadb
import requests
from chromadb.config import Settings as ChromaSettings

from movielab import providers
from movielab.collect.collector import Collector
from movielab.collect.manifest import Manifest
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.config import Settings
from movielab.core.domain import DomainProfile
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.raw_store import RawStore
from movielab.data.wiki_api import WikiApiSource, WikiHttpClient, shared_throttle
from movielab.data.wiki_bundle import WikiBundleSource
from movielab.index.doc_indexer import DocIndexer
from movielab.index.store import VectorStore
from movielab.rag.graph import build_graph
from movielab.rag.retriever import Retriever
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
        self.http = http  # 주지 않으면 wiki_client를 만들 때 requests.Session을 만든다 (NF2006)
        self._llm = llm
        self._embeddings = embeddings
        self.catalog = Catalog(lambda: self._load_items())
        self._store: VectorStore | None = None
        self._wiki_client: WikiHttpClient | None = None
        self._lock = threading.Lock()
        self._bundle_source: WikiBundleSource | None = None
        self._collector: Collector | None = None

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
            self._store = VectorStore(
                client, self.settings, embeddings_factory=lambda: self.embeddings
            )
        return self._store

    @property
    def wiki_client(self) -> WikiHttpClient:
        """위키백과 API 클라이언트. 연락처(WIKI_CONTACT)가 없으면 요청 시 안내 오류 (NF2006)."""
        with self._lock:
            if self._wiki_client is None:
                wiki = self.settings.wiki
                self._wiki_client = WikiHttpClient(
                    self.settings,
                    self.settings.secrets.wiki_contact,
                    session=self.http if self.http is not None else requests.Session(),
                    throttle=shared_throttle(wiki.api_url, wiki.min_interval_sec),
                )
        return self._wiki_client

    @property
    def bundle_source(self) -> WikiBundleSource:
        """제공 문서 묶음 소스 — 묶음(약 3,700 파일)은 프로세스에서 한 번만 읽는다."""
        with self._lock:
            if self._bundle_source is None:
                collect = self.settings.collect
                self._bundle_source = WikiBundleSource(
                    self.settings.path("wiki_bundle"),
                    body_chars=collect.bundle_body_chars,
                    snippet_radius=collect.bundle_snippet_radius,
                    intro_chars=collect.intro_chars,
                )
        return self._bundle_source

    @property
    def manifest(self) -> Manifest:
        """수집 캐시 (NF2002). LLM · 키 없이도 쓸 수 있다 (예: 캐시 초기화)."""
        cache = self.settings.cache
        return Manifest(
            self.settings.path("manifest"),
            lock_timeout_sec=cache.lock_timeout_sec,
            lock_poll_sec=cache.lock_poll_sec,
            io_retries=cache.io_retries,
            io_retry_wait_sec=cache.io_retry_wait_sec,
        )

    @property
    def raw_store(self) -> RawStore:
        """수집 원문 저장소 (F2004). 재색인 스크립트도 여기서 원문을 읽는다."""
        return RawStore(self.settings.path("raw_dir"))

    def doc_indexer(self, **chunking: int) -> DocIndexer:
        """위키 문서 색인기 (F2005). 인자를 주면 청크 값을 이번 실행만 덮어쓴다."""
        return DocIndexer(self.store, source_type=self.profile.doc_source_label, **chunking)

    def retriever(self, top_k: int | None = None) -> Retriever:
        """근거 검색기 (F2006). `top_k`를 주면 이번 검색만 설정 값을 덮어쓴다."""
        return Retriever(self.store, top_k=top_k, meta_title=self.profile.meta_title)

    def rag_graph(self, *, llm: Any = None, top_k: int | None = None) -> Any:
        """retrieve → generate 그래프 (F2007). `llm`을 주면 그것을 쓴다(구조 출력 등)."""
        chat = self.llm if llm is None else llm
        return build_graph(self.retriever(top_k=top_k), chat, self.profile)

    def make_collector(self, *, dry_run: bool = False) -> Collector:
        """문서 수집기 (F2004). 연락처가 없으면 API 소스 없이(묶음으로) 동작한다.

        수집 캐시(NF2002)는 파일 매니페스트를, 색인은 청크 색인기(F2005)를 쓴다.
        `dry_run`이면 색인 · 캐시 기록을 하지 않는다(원문 저장까지만).
        """
        settings = self.settings
        api_source = WikiApiSource(self.wiki_client) if settings.secrets.wiki_contact else None
        indexer = None if dry_run else self.doc_indexer()  # 색인 · 대조가 같은 청크 설정을 쓴다
        return Collector(
            api_source=api_source,
            bundle_source=self.bundle_source,
            extractor=QueryExtractor(self.llm, self.profile, settings),
            selector=CandidateSelector(self.llm, self.profile, settings),
            raw_store=self.raw_store,
            profile=self.profile,
            settings=settings,
            manifest=None if dry_run else self.manifest,
            indexer=None if indexer is None else indexer.index_document,
            indexed_pages=None if indexer is None else indexer.page_ids,
        )

    @property
    def collector(self) -> Collector:
        """앱 · 스크립트가 쓰는 수집기 — 한 번만 만든다."""
        if self._collector is None:
            self._collector = self.make_collector()
        return self._collector


def build_services(
    settings: Settings,
    *,
    llm: Any = None,
    embeddings: Any = None,
    http: Any = None,
    profile: DomainProfile | None = None,
) -> Services:
    return Services(settings, profile or MOVIE_PROFILE, llm=llm, embeddings=embeddings, http=http)
