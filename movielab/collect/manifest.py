"""수집 매니페스트(캐시) — 이미 수집한 질문 · 검색어 · 문서를 영화별로 기록한다 (SPEC-NF2002).

제공 `wiki_manifest.json`과 호환되는 형식(`keywords` · `titles` · `page_ids` · `chunks` ·
`collected_at`)에 `questions` · `rejected_page_ids` · `item_doc_page_id`를 더한다.
쓰기는 임시 파일에 쓴 뒤 바꿔 넣고, 깨진 파일은 백업해 두고 빈 매니페스트로 시작한다.
`NullManifest`는 아무것도 기억하지 않는다 — 캐시 없이도 수집 절차가 동작한다.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

from movielab.core.text import normalize_key

logger = logging.getLogger(__name__)


class NullManifest:
    def cached_queries(self, item_id: str, question: str) -> list[str] | None:
        return None

    def has_keyword(self, item_id: str, query: str) -> bool:
        return False

    def has_page(self, item_id: str, page_id: str) -> bool:
        return False

    def item_doc_page_id(self, item_id: str) -> str | None:
        return None

    def title_of(self, item_id: str, page_id: str) -> str | None:
        return None

    def record_question(self, item_id: str, question: str, queries: list[str]) -> None:
        pass

    def record_keyword(self, item_id: str, query: str) -> None:
        pass

    def record_item_doc(self, item_id: str, page_id: str) -> None:
        pass

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> None:
        pass

    def reset(self, item_id: str | None = None) -> None:
        pass


def _empty_entry() -> dict[str, Any]:
    return {
        "keywords": [],
        "titles": [],
        "page_ids": [],
        "questions": {},
        "rejected_page_ids": [],
        "item_doc_page_id": None,
        "chunks": 0,
        "collected_at": None,
    }


class Manifest(NullManifest):
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = self._read()

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("최상위가 객체가 아니다")
            return data
        except (OSError, ValueError) as exc:
            backup = self.path.with_name(f"{self.path.name}.broken-{datetime.now():%Y%m%d%H%M%S}")
            os.replace(self.path, backup)
            logger.warning("매니페스트가 깨져 %s로 옮기고 새로 시작한다 (%s)", backup.name, exc)
            return {}

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def _entry(self, item_id: str) -> dict[str, Any]:
        entry = self._data.setdefault(str(item_id), _empty_entry())
        for key, value in _empty_entry().items():
            entry.setdefault(key, value)
        return entry

    def _peek(self, item_id: str) -> dict[str, Any]:
        return self._data.get(str(item_id)) or {}

    # --- 조회 ---

    def cached_queries(self, item_id: str, question: str) -> list[str] | None:
        queries = (self._peek(item_id).get("questions") or {}).get(normalize_key(question))
        return list(queries) if queries is not None else None

    def has_keyword(self, item_id: str, query: str) -> bool:
        keys = {normalize_key(k) for k in self._peek(item_id).get("keywords") or []}
        return normalize_key(query) in keys

    def has_page(self, item_id: str, page_id: str) -> bool:
        return str(page_id) in (self._peek(item_id).get("page_ids") or [])

    def item_doc_page_id(self, item_id: str) -> str | None:
        return self._peek(item_id).get("item_doc_page_id")

    def title_of(self, item_id: str, page_id: str) -> str | None:
        entry = self._peek(item_id)
        pages, titles = entry.get("page_ids") or [], entry.get("titles") or []
        return titles[pages.index(str(page_id))] if str(page_id) in pages else None

    # --- 기록 (검색 · 색인을 마친 뒤에만 부른다) ---

    def _touch(self, entry: dict[str, Any]) -> None:
        entry["collected_at"] = date.today().isoformat()
        self._write()

    def record_question(self, item_id: str, question: str, queries: list[str]) -> None:
        with self._lock:
            entry = self._entry(item_id)
            entry["questions"][normalize_key(question)] = list(queries)
            self._touch(entry)

    def record_keyword(self, item_id: str, query: str) -> None:
        with self._lock:
            entry = self._entry(item_id)
            if normalize_key(query) not in {normalize_key(k) for k in entry["keywords"]}:
                entry["keywords"].append(query)
            self._touch(entry)

    def record_item_doc(self, item_id: str, page_id: str) -> None:
        with self._lock:
            entry = self._entry(item_id)
            entry["item_doc_page_id"] = str(page_id)
            self._touch(entry)

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> None:
        with self._lock:
            entry = self._entry(item_id)
            page_id = str(page_id)
            if rejected:
                if page_id not in entry["rejected_page_ids"]:
                    entry["rejected_page_ids"].append(page_id)
            elif page_id not in entry["page_ids"]:
                entry["page_ids"].append(page_id)
                entry["titles"].append(title)
                entry["chunks"] = int(entry.get("chunks") or 0) + int(chunks)
            self._touch(entry)

    def reset(self, item_id: str | None = None) -> None:
        with self._lock:
            if item_id is None:
                self._data = {}
            else:
                self._data.pop(str(item_id), None)
            self._write()
