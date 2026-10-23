"""제공 문서 묶음(movielab_wiki/) 소스 — 위키백과 호출이 막힐 때의 대비책 (SPEC-F2004 §3.1).

외부 호출 없이 묶음 전체를 메모리에 올려 제목 · 본문으로 검색한다.
검색 → P2 선별 → 수집 절차는 API 소스와 똑같이 돈다(검색어 추출 · 선별 코드는 그대로 실행).
순위는 단계(제목 일치 > 제목 포함 > 본문만 일치)가 먼저이고, 같은 단계 안에서
현재 항목 문서 → 본문 등장 횟수 순이다.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from movielab.core.text import normalize_key
from movielab.core.types import Candidate, SourceDocument

logger = logging.getLogger(__name__)

TIER_EXACT, TIER_TITLE, TIER_BODY = 2, 1, 0


@dataclass(frozen=True)
class _Doc:
    page_id: str
    title: str
    url: str
    text: str
    source: str
    collected_at: str


def _query_pattern(query: str) -> re.Pattern[str]:
    """공백 차이를 무시하고 원문에서 검색어를 찾는 정규식."""
    words = [re.escape(word) for word in query.split()]
    return re.compile(r"\s+".join(words), re.IGNORECASE)


class WikiBundleSource:
    kind = "bundle"

    def __init__(
        self,
        bundle_dir: Path,
        *,
        body_chars: int = 2000,
        snippet_radius: int = 150,
        intro_chars: int = 300,
    ) -> None:
        """길이 값은 container가 `settings.collect`(A-23)에서 넘긴다."""
        self.bundle_dir = Path(bundle_dir)
        self.body_chars = body_chars
        self.snippet_radius = snippet_radius
        self.intro_chars = intro_chars
        self._docs: dict[str, _Doc] | None = None
        self._by_item: dict[str, set[str]] = {}

    def _load(self) -> dict[str, _Doc]:
        if self._docs is None:
            docs: dict[str, _Doc] = {}
            for path in sorted(self.bundle_dir.glob("*.json")):
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    logger.warning("묶음 파일을 읽지 못함: %s", path.name)
                    continue
                page_id = str(raw["page_id"])
                docs.setdefault(
                    page_id,
                    _Doc(
                        page_id,
                        raw["title"],
                        raw.get("url", ""),
                        raw.get("text", ""),
                        raw.get("source", ""),
                        raw.get("collected_at", ""),
                    ),
                )
                self._by_item.setdefault(str(raw.get("movie_id", "")), set()).add(page_id)
            self._docs = docs
            logger.info("문서 묶음 %d건 로드 (%s)", len(docs), self.bundle_dir)
        return self._docs

    def _snippet(self, text: str, pattern: re.Pattern[str]) -> str:
        match = pattern.search(text)
        if match is None:
            return " ".join(text[: self.snippet_radius * 2].split())
        start = max(0, match.start() - self.snippet_radius)
        return " ".join(text[start : match.end() + self.snippet_radius].split())

    def _rank(self, doc: _Doc, key: str) -> tuple[int, int] | None:
        """(단계, 본문 등장 횟수). 맞지 않으면 None."""
        title = normalize_key(doc.title)
        body_hits = normalize_key(doc.text[: self.body_chars]).count(key)
        if title == key:
            return TIER_EXACT, body_hits
        if key in title:
            return TIER_TITLE, body_hits
        return (TIER_BODY, body_hits) if body_hits else None

    def search(self, query: str, limit: int, item_id: str | None = None) -> list[Candidate]:
        key = normalize_key(query)
        if not key:
            return []
        docs = self._load()
        current = self._by_item.get(str(item_id), set()) if item_id else set()
        ranked: list[tuple[tuple[int, int, int], str, _Doc]] = []
        for doc in docs.values():
            rank = self._rank(doc, key)
            if rank is not None:
                tier, hits = rank
                ranked.append(((tier, int(doc.page_id in current), hits), doc.title, doc))
        ranked.sort(key=lambda entry: (tuple(-v for v in entry[0]), entry[1]))
        pattern = _query_pattern(query)
        return [
            Candidate(
                page_id=doc.page_id,
                title=doc.title,
                snippet=self._snippet(doc.text, pattern),
                size=len(doc.text),
                query=query,
                url=doc.url,
                disambiguation=doc.title.endswith("(동음이의)"),
            )
            for _, _, doc in ranked[:limit]
        ]

    def resolve_titles(self, titles: list[str]) -> list[Candidate]:
        by_title = {normalize_key(d.title): d for d in self._load().values()}
        found: list[Candidate] = []
        for requested in titles:
            doc = by_title.get(normalize_key(requested))
            if doc is not None:
                found.append(
                    Candidate(
                        page_id=doc.page_id,
                        title=doc.title,
                        snippet=doc.text[: self.intro_chars],
                        url=doc.url,
                        matched_title=requested,
                        disambiguation=doc.title.endswith("(동음이의)"),
                    )
                )
        return found

    def fetch(self, page_id: str) -> SourceDocument | None:
        doc = self._load().get(str(page_id))
        if doc is None:
            return None
        return SourceDocument(
            page_id=doc.page_id,
            title=doc.title,
            url=doc.url,
            text=doc.text,
            source=doc.source,
            movie_id="",
            related_movie="",
            search_query="",
            collected_at=doc.collected_at,
        )
