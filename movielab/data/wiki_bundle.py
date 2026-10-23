"""제공 문서 묶음(movielab_wiki/) 소스 — 위키백과 호출이 막힐 때의 대비책 (SPEC-F2004 §3.1).

외부 호출 없이 묶음 전체를 메모리에 올려 제목 · 본문으로 검색한다.
검색 → P2 선별 → 수집 절차는 API 소스와 똑같이 돈다(검색어 추출 · 선별 코드는 그대로 실행).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from movielab.core.text import normalize_key
from movielab.core.types import Candidate, SourceDocument

logger = logging.getLogger(__name__)

BODY_WINDOW = 2000  # 본문 검색 범위(앞부분)
SNIPPET_RADIUS = 150
SCORE_EXACT, SCORE_TITLE, CURRENT_ITEM_BONUS = 100, 50, 30


@dataclass(frozen=True)
class _Doc:
    page_id: str
    title: str
    url: str
    text: str
    source: str
    collected_at: str


class WikiBundleSource:
    kind = "bundle"

    def __init__(self, bundle_dir: Path) -> None:
        self.bundle_dir = Path(bundle_dir)
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

    @staticmethod
    def _snippet(text: str, key: str) -> str:
        position = normalize_key(text).find(key)
        if position < 0:
            return " ".join(text[: SNIPPET_RADIUS * 2].split())
        start = max(0, position - SNIPPET_RADIUS)
        return " ".join(text[start : position + len(key) + SNIPPET_RADIUS].split())

    def _score(self, doc: _Doc, key: str) -> int:
        title = normalize_key(doc.title)
        if title == key:
            return SCORE_EXACT
        if key in title:
            return SCORE_TITLE
        return normalize_key(doc.text[:BODY_WINDOW]).count(key)

    def search(self, query: str, limit: int, item_id: str | None = None) -> list[Candidate]:
        key = normalize_key(query)
        if not key:
            return []
        docs = self._load()
        current = self._by_item.get(str(item_id), set()) if item_id else set()
        scored: list[tuple[int, str, _Doc]] = []
        for doc in docs.values():
            score = self._score(doc, key)
            if score > 0:
                bonus = CURRENT_ITEM_BONUS if doc.page_id in current else 0
                scored.append((score + bonus, doc.title, doc))
        scored.sort(key=lambda entry: (-entry[0], entry[1]))
        return [
            Candidate(
                page_id=doc.page_id,
                title=doc.title,
                snippet=self._snippet(doc.text, key),
                size=len(doc.text),
                query=query,
                url=doc.url,
                disambiguation=doc.title.endswith("(동음이의)"),
            )
            for _, _, doc in scored[:limit]
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
                        snippet=doc.text[:300],
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
