"""가짜 문서 소스 (SPEC-F2004 DocumentSource). 등록한 후보 · 문서를 돌려주고 호출을 기록한다."""

from __future__ import annotations

import dataclasses

from movielab.core.errors import ExternalSourceUnavailableError
from movielab.core.types import Candidate, SourceDocument


def make_doc(page_id: str, title: str, text: str | None = None) -> SourceDocument:
    body = text if text is not None else f"[합성] {title} 문서 본문. " * 20
    return SourceDocument(
        page_id=page_id,
        title=title,
        url=f"https://wiki.example.invalid/wiki/{title.replace(' ', '_')}",
        text=body,
        source="한국어 위키백과",
        movie_id="",
        related_movie="",
        search_query="",
        collected_at="2026-09-01",
    )


class FakeSource:
    """`docs`: page_id → SourceDocument, `search_results`: 검색어 → page_id 목록,
    `titles`: 제목 → (page_id, 도입부, 동음이의 여부). `fail_calls`번까지 호출하면 외부 출처 오류.
    """

    def __init__(self, kind: str = "api", *, fail_calls: int = 0) -> None:
        self.kind = kind
        self.docs: dict[str, SourceDocument] = {}
        self.search_results: dict[str, list[str]] = {}
        self.titles: dict[str, tuple[str, str, bool]] = {}
        self.calls: list[tuple[str, object]] = []
        self.fail_calls = fail_calls

    def add(self, doc: SourceDocument, *, queries=(), title_intro: str | None = None,
            disambiguation: bool = False) -> FakeSource:  # fmt: skip
        self.docs[doc.page_id] = doc
        for query in queries:
            self.search_results.setdefault(query, []).append(doc.page_id)
        if title_intro is not None:
            self.titles[doc.title] = (doc.page_id, title_intro, disambiguation)
        return self

    def _maybe_fail(self) -> None:
        if len(self.calls) <= self.fail_calls:
            raise ExternalSourceUnavailableError("가짜 소스 장애")

    def _candidate(self, page_id: str, query: str, requested: str = "") -> Candidate:
        doc = self.docs[page_id]
        return Candidate(
            page_id=page_id,
            title=doc.title,
            snippet=doc.text[:80],
            size=len(doc.text),
            query=query,
            url=doc.url,
            matched_title=requested or doc.title,
            disambiguation=doc.title.endswith("(동음이의)"),
        )

    def search(self, query: str, limit: int, item_id: str | None = None) -> list[Candidate]:
        self.calls.append(("search", query))
        self._maybe_fail()
        return [self._candidate(pid, query) for pid in self.search_results.get(query, [])][:limit]

    def resolve_titles(self, titles: list[str]) -> list[Candidate]:
        self.calls.append(("resolve", tuple(titles)))
        self._maybe_fail()
        found = []
        for title in titles:
            if title in self.titles:
                page_id, intro, disambiguation = self.titles[title]
                candidate = self._candidate(page_id, title, requested=title)
                found.append(
                    dataclasses.replace(candidate, snippet=intro, disambiguation=disambiguation)
                )
        return found

    def fetch(self, page_id: str) -> SourceDocument | None:
        self.calls.append(("fetch", page_id))
        self._maybe_fail()
        return self.docs.get(page_id)

    def fetched(self) -> list[str]:
        return [str(arg) for name, arg in self.calls if name == "fetch"]
