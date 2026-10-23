"""외부 문서 수집 오케스트레이션 (SPEC-F2004 §3.3).

검색어 추출(P1) → 항목 자체 문서 판별 → 검색 → 제외 규칙 → 후보 선별(P2) → 본문 수집 · 저장 → 색인.
항목 자체 문서는 P2 · 개수 상한 · 길이 규칙과 상관없이 항상 수집한다.
`auto` 모드에서 위키백과 API를 못 쓰면 그 수집의 남은 단계를 제공 묶음으로 바꾼다.
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
from movielab.core.errors import ExternalSourceUnavailableError
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

    # --- 수집 ---

    def collect(
        self, item: ItemRecord, question: str, on_progress: Progress | None = None
    ) -> CollectReport:
        def progress(stage: str, **info: Any) -> None:
            if on_progress is not None:
                on_progress(stage, info)

        started = time.perf_counter()
        report = CollectReport(item_id=item.item_id, question=question)
        state = {"source": self._initial_source(report)}
        collect_settings = self.settings.collect

        # 1. 검색어 추출 (질문 캐시 적중이면 P1 생략)
        progress("extract_queries")
        cached = self.manifest.cached_queries(item.item_id, question)
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
        resolved = self._call(report, state, "resolve_titles", self.profile.item_doc_queries(item))
        item_doc = self.profile.pick_item_doc(item, resolved)
        if item_doc is None:
            report.notices.append("ITEM_DOC_NOT_FOUND")
        else:
            report.item_doc_title = item_doc.title

        # 3. 검색 — 후보를 page_id로 합친다. 항목 자체 문서는 후보에서 뺀다(강제 포함 대상)
        pool: dict[str, Candidate] = {}
        searched: list[str] = []
        todo = [q for q in queries if not self.manifest.has_keyword(item.item_id, q)]
        report.cached_queries = [q for q in queries if q not in todo]
        for number, query in enumerate(todo, start=1):
            progress("search", query=query, current=number, total=len(todo))
            results = self._call(
                report, state, "search", query, int(collect_settings.search_limit), item.item_id
            )
            searched.append(query)
            for candidate in results:
                if item_doc is not None and candidate.page_id == item_doc.page_id:
                    continue
                pool.setdefault(candidate.page_id, candidate)
        report.candidates = list(pool.values())

        # 4. 제외 규칙 (본문 전): 이미 수집, 동음이의
        progress("filter")
        eligible: list[Candidate] = []
        for candidate in report.candidates:
            if self.manifest.has_page(item.item_id, candidate.page_id):
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

        # 6. 본문 수집 · 저장 — 항목 자체 문서가 먼저, 길이 규칙 면제
        targets: list[tuple[Candidate, bool]] = []
        if item_doc is not None and not self.manifest.has_page(item.item_id, item_doc.page_id):
            targets.append((item_doc, True))
        targets += [(c, False) for c in selection.selected]
        documents: list[SourceDocument] = []
        for number, (candidate, is_item_doc) in enumerate(targets, start=1):
            progress("fetch", title=candidate.title, current=number, total=len(targets))
            doc = self._call(report, state, "fetch", candidate.page_id)
            if doc is None:
                report.rejected.append(
                    Rejection(candidate.page_id, candidate.title, "fetch_failed")
                )
                continue
            if not is_item_doc and len(doc.text) < int(collect_settings.min_doc_chars):
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

        # 7. 색인 (F2005 색인기가 연결되면)
        for doc in documents:
            progress("index", title=doc.title)
            chunks = self.indexer(doc) if self.indexer is not None else 0
            report.indexed_chunks += chunks
            report.indexed_titles.append(doc.title)
            self.manifest.record_page(item.item_id, doc.page_id, doc.title, chunks)

        # 8. 기록
        for query in searched:
            self.manifest.record_keyword(item.item_id, query)
        self.manifest.record_question(item.item_id, question, queries)
        report.source_used = state["source"].kind
        report.timings["collect"] = time.perf_counter() - started
        progress("done", titles=report.indexed_titles, rejected=len(report.rejected))
        return report
