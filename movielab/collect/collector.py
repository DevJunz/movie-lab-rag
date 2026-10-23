"""외부 문서 수집 오케스트레이션 (SPEC-F2004 §3.3).

검색어 추출(P1) → 항목 자체 문서 판별 → 검색 → 제외 규칙 → 후보 선별(P2) → 본문 수집 · 저장 → 색인.
항목 자체 문서는 P2 · 개수 상한 · 길이 규칙과 상관없이 항상 수집한다.
`auto` 모드에서 위키백과 API를 못 쓰면 그 수집의 남은 단계를 제공 묶음으로 바꾼다.
문서 하나의 조회 · 색인 실패는 그 문서만 건너뛴다(사유를 남기고 계속).
"""

from __future__ import annotations

import dataclasses
import logging
import time
from collections.abc import Callable
from typing import Any

from movielab.collect.manifest import NullManifest
from movielab.collect.query_extractor import QueryExtractor
from movielab.collect.selector import CandidateSelector
from movielab.core.domain import DomainProfile
from movielab.core.errors import ExternalSourceUnavailableError, MovieLabUserError
from movielab.core.types import Candidate, CollectReport, ItemRecord, Rejection, SourceDocument

logger = logging.getLogger(__name__)

Progress = Callable[[str, dict[str, Any]], None]


class Collector:
    def __init__(
        self,
        *,
        api_source: Any | None,
        bundle_source: Any,
        extractor: QueryExtractor,
        selector: CandidateSelector,
        raw_store: Any,
        profile: DomainProfile,
        settings: Any,
        manifest: Any | None = None,
        indexer: Callable[[SourceDocument], int] | None = None,
        indexed_pages: Callable[[str], set[str]] | None = None,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        self.api_source = api_source
        self.bundle_source = bundle_source
        self.extractor = extractor
        self.selector = selector
        self.raw_store = raw_store
        self.profile = profile
        self.settings = settings
        self.manifest = manifest or NullManifest()
        self.indexer = indexer
        # 그 영화의 색인에 청크가 있는 문서 (NF2002: 매니페스트 기록과 대조)
        self.indexed_pages = indexed_pages
        self.clock = clock

    # --- 소스 선택 · 대체 (§3.2) ---

    def _initial_source(self, report: CollectReport) -> Any:
        mode = self.settings.collect.source
        if mode == "bundle":
            return self.bundle_source
        if self.api_source is None:
            if mode == "api":
                raise ExternalSourceUnavailableError("위키백과 API 연락처(WIKI_CONTACT)가 없다")
            report.notices.append("SOURCE_FALLBACK")
            return self.bundle_source
        return self.api_source

    def _is_configured_source(self, source: Any) -> bool:
        """설정한 소스로 처리했는가 — 대체 소스로 검색한 검색어는 캐시에 남기지 않는다."""
        if self.settings.collect.source == "bundle":
            return source is self.bundle_source
        return source is self.api_source

    def _call(self, report: CollectReport, state: dict[str, Any], method: str, *args: Any) -> Any:
        source = state["source"]
        try:
            return getattr(source, method)(*args)
        except ExternalSourceUnavailableError:
            if self.settings.collect.source != "auto" or source is self.bundle_source:
                raise
            logger.warning("위키백과 API를 쓸 수 없어 제공 묶음으로 전환한다 (%s)", method)
            state["source"] = self.bundle_source
            report.notices.append("SOURCE_FALLBACK")
            return getattr(self.bundle_source, method)(*args)

    def _resolve_item_doc(
        self,
        manifest: NullManifest,
        item: ItemRecord,
        report: CollectReport,
        state: dict[str, Any],
    ) -> Candidate | None:
        profile = self.profile
        known = manifest.item_doc_page_id(item.item_id)
        if known is not None:  # 이미 수집한 항목 자체 문서 — 제목 조회 생략 (NF2002)
            report.item_doc_title = manifest.title_of(item.item_id, known)
            return None
        if profile.item_doc_queries is None or profile.pick_item_doc is None:
            report.notices.append("ITEM_DOC_NOT_FOUND")
            return None
        resolved = self._call(report, state, "resolve_titles", profile.item_doc_queries(item))
        item_doc = profile.pick_item_doc(item, resolved)
        if item_doc is None:
            report.notices.append("ITEM_DOC_NOT_FOUND")
        else:
            report.item_doc_title = item_doc.title
        return item_doc

    # --- 수집 ---

    def collect(
        self, item: ItemRecord, question: str, on_progress: Progress | None = None
    ) -> CollectReport:
        def progress(stage: str, **info: Any) -> None:
            if on_progress is not None:
                on_progress(stage, info)

        started = self.clock()
        report = CollectReport(item_id=item.item_id, question=question)
        collect_settings = self.settings.collect
        manifest = self.manifest

        # 0. 캐시 (NF2002). 매니페스트는 힌트일 뿐 — 기록된 문서 중 색인에 없는 것이 있으면
        # (chroma 삭제 · 일부 손실 · 이전 초기화 실패) 캐시를 비운다. 비우지 못하면 이번 수집은
        # 옛 기록을 믿지 않도록 매니페스트를 읽지도 쓰지도 않는다
        recorded = manifest.page_ids(item.item_id)
        if (
            self.indexed_pages is not None
            and recorded
            and not recorded <= {str(p) for p in self.indexed_pages(item.item_id)}
        ):
            logger.warning("색인에 없는 문서 기록이 있어 %s의 수집 캐시를 비운다", item.item_id)
            if not manifest.reset(item.item_id):
                logger.warning("수집 캐시를 비우지 못해 이번 수집은 캐시 없이 한다")
                manifest = NullManifest()
        # 같은 질문 · 같은 검색어를 이미 수집했으면 외부 호출 없이 끝낸다
        cached = manifest.cached_queries(item.item_id, question)
        if cached is not None and all(manifest.has_keyword(item.item_id, q) for q in cached):
            progress("cache_hit", queries=cached)
            report.queries = list(cached)
            report.cached_queries = list(cached)
            report.notices.append("CACHE_HIT")
            report.source_used = "cache"
            report.timings["collect"] = self.clock() - started
            progress("done", titles=[], rejected=0)
            return report

        state = {"source": self._initial_source(report)}

        # 1. 검색어 추출 (질문 캐시 적중이면 P1 생략)
        progress("extract_queries")
        if cached is not None:
            queries = list(cached)
        else:
            plan = self.extractor.extract(item, question)
            queries = plan.all
            if plan.fallback:
                report.notices.append("P1_FALLBACK")
        report.queries = queries
        progress("extract_queries", queries=queries)

        # 2. 항목 자체 문서
        progress("resolve_item_doc")
        item_doc = self._resolve_item_doc(manifest, item, report, state)

        item_doc_id = (
            item_doc.page_id if item_doc is not None else manifest.item_doc_page_id(item.item_id)
        )

        # 3. 검색 — 후보를 page_id로 합친다. 항목 자체 문서는 후보에서 뺀다(강제 포함 대상)
        pool: dict[str, Candidate] = {}
        searched: list[str] = []  # 설정한 소스로 검색을 마친 검색어 (캐시 기록 대상)
        todo = [q for q in queries if not manifest.has_keyword(item.item_id, q)]
        report.cached_queries = [q for q in queries if q not in todo]
        for number, query in enumerate(todo, start=1):
            progress("search", query=query, current=number, total=len(todo))
            results = self._call(
                report, state, "search", query, int(collect_settings.search_limit), item.item_id
            )
            if self._is_configured_source(state["source"]):
                searched.append(query)
            for candidate in results:
                if candidate.page_id == item_doc_id:
                    continue
                pool.setdefault(candidate.page_id, candidate)
        report.candidates = list(pool.values())

        # 4. 제외 규칙 (본문 전): 이미 수집, 동음이의
        progress("filter")
        eligible: list[Candidate] = []
        for candidate in report.candidates:
            if manifest.has_page(item.item_id, candidate.page_id):
                report.rejected.append(
                    Rejection(candidate.page_id, candidate.title, "already_collected")
                )
            elif candidate.disambiguation:
                report.rejected.append(
                    Rejection(candidate.page_id, candidate.title, "disambiguation")
                )
            else:
                eligible.append(candidate)

        # 5. 후보 선별 (P2)
        progress("select", candidates=len(eligible))
        selection = self.selector.select(item, question, eligible)
        report.selected = selection.selected
        report.rejected.extend(selection.rejected)

        # 6. 본문 수집 · 저장 — 항목 자체 문서가 먼저, 길이 규칙 면제. 문서 단위로 실패를 격리
        targets: list[tuple[Candidate, bool]] = []
        if item_doc is not None and not manifest.has_page(item.item_id, item_doc.page_id):
            targets.append((item_doc, True))
        targets += [(c, False) for c in selection.selected]
        documents: list[SourceDocument] = []
        for number, (candidate, is_item_doc) in enumerate(targets, start=1):
            progress("fetch", title=candidate.title, current=number, total=len(targets))
            try:
                doc = self._call(report, state, "fetch", candidate.page_id)
            except Exception:
                logger.exception("본문 조회 실패: %s", candidate.title)
                doc = None
            if doc is None:
                report.rejected.append(
                    Rejection(candidate.page_id, candidate.title, "fetch_failed")
                )
                continue
            # 항목 자체 문서는 길이 규칙 면제 — 단 본문이 비어 있으면 색인할 수 없으므로 버린다
            too_short = len(doc.text) < int(collect_settings.min_doc_chars)
            if (too_short and not is_item_doc) or not doc.text.strip():
                report.rejected.append(Rejection(candidate.page_id, candidate.title, "too_short"))
                continue
            doc = dataclasses.replace(
                doc,
                movie_id=item.item_id,
                related_movie=item.title,
                search_query=candidate.query or candidate.matched_title or candidate.title,
                is_item_doc=is_item_doc,
            )
            report.saved_paths.append(self.raw_store.save(doc))
            documents.append(doc)

        # 7. 색인 (F2005 색인기가 연결되면) — 키 없음 같은 안내 오류는 모든 문서에 같으므로 알린다
        recorded_pages: list[tuple[str, str, int]] = []
        item_doc_page_id: str | None = None
        for doc in documents:
            progress("index", title=doc.title)
            if self.indexer is None:
                chunks = 0
            else:
                try:
                    chunks = self.indexer(doc)
                except MovieLabUserError:
                    raise
                except Exception:
                    logger.exception("색인 실패: %s", doc.title)
                    chunks = -1
                if chunks <= 0:
                    report.rejected.append(Rejection(doc.page_id, doc.title, "index_failed"))
                    continue
            report.indexed_chunks += chunks
            report.indexed_titles.append(doc.title)
            if self.indexer is None:
                continue  # 색인하지 않은 문서는 수집됨으로 기록하지 않는다 (NF2002 §3.2)
            recorded_pages.append((doc.page_id, doc.title, chunks))
            if doc.is_item_doc:
                item_doc_page_id = doc.page_id

        # 8. 기록 — 수집 한 번의 결과를 한 번에(전부 또는 하나도 안 되게) 남긴다.
        # 검색어 · 질문은 완전히 성공했을 때만(실패한 문서는 다음 질문 때 재시도)
        failed = any(r.reason in ("fetch_failed", "index_failed") for r in report.rejected)
        if self.indexer is not None:
            complete = not failed
            manifest.record_collection(
                item.item_id,
                pages=recorded_pages,
                item_doc_page_id=item_doc_page_id,
                keywords=searched if complete else [],
                question=(question, queries) if complete and len(searched) == len(todo) else None,
            )
        report.source_used = state["source"].kind
        report.timings["collect"] = self.clock() - started
        progress("done", titles=report.indexed_titles, rejected=len(report.rejected))
        return report
