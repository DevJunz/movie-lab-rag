"""수집 매니페스트(캐시) — 이미 수집한 질문 · 검색어 · 문서를 영화별로 기록한다 (SPEC-NF2002).

제공 `wiki_manifest.json`과 호환되는 형식(`keywords` · `titles` · `page_ids` · `chunks` ·
`collected_at`)에 `questions` · `rejected_page_ids` · `item_doc_page_id`를 더한다.

여러 인스턴스 · 프로세스(앱과 `--reset-cache` 스크립트 등)가 같은 파일을 쓰므로, 파일이 바뀌었으면
읽기 · 쓰기 전에 다시 읽는다. 쓰기는 고유한 임시 파일에 쓴 뒤 바꿔 넣는다. 깨졌거나 구조가 틀린
파일은 백업해 두고 빈 매니페스트로 시작한다. `NullManifest`는 아무것도 기억하지 않는다.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import uuid
from collections.abc import Callable
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

    def has_any(self, item_id: str) -> bool:
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


_LIST_FIELDS = ("keywords", "titles", "page_ids", "rejected_page_ids")


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


def _valid(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    for entry in data.values():
        if not isinstance(entry, dict):
            return False
        if any(not isinstance(entry.get(key, []), list) for key in _LIST_FIELDS):
            return False
        if not isinstance(entry.get("questions", {}), dict):
            return False
    return True


class Manifest(NullManifest):
    _backup_counter = itertools.count()

    def __init__(
        self,
        path: Path,
        *,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.path = Path(path)
        self.today = today
        self.now = now
        self._lock = threading.Lock()
        self._mtime: int | None = None
        self._data: dict[str, dict[str, Any]] = {}
        self._refresh()

    # --- 파일 ---

    def _stat(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except FileNotFoundError:
            return None

    def _backup(self, reason: str) -> None:
        stamp = f"{self.now():%Y%m%d%H%M%S%f}-{next(self._backup_counter)}"
        backup = self.path.with_name(f"{self.path.name}.broken-{stamp}")
        os.replace(self.path, backup)
        logger.warning("매니페스트를 %s로 옮기고 새로 시작한다 (%s)", backup.name, reason)

    def _refresh(self) -> None:
        """파일이 바뀌었으면 다시 읽는다 (다른 인스턴스 · 프로세스가 쓴 내용 반영)."""
        mtime = self._stat()
        if mtime == self._mtime:
            return
        if mtime is None:
            self._data, self._mtime = {}, None
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self._backup(f"읽기 실패: {exc}")
            self._data, self._mtime = {}, None
            return
        if not _valid(data):
            self._backup("구조가 맞지 않음")
            self._data, self._mtime = {}, None
            return
        self._data, self._mtime = data, mtime

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)
        self._mtime = self._stat()

    def _entry(self, item_id: str) -> dict[str, Any]:
        entry = self._data.setdefault(str(item_id), _empty_entry())
        for key, value in _empty_entry().items():
            entry.setdefault(key, value)
        return entry

    def _peek(self, item_id: str) -> dict[str, Any]:
        with self._lock:
            self._refresh()
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

    def has_any(self, item_id: str) -> bool:
        return bool(self._peek(item_id))

    def item_doc_page_id(self, item_id: str) -> str | None:
        return self._peek(item_id).get("item_doc_page_id")

    def title_of(self, item_id: str, page_id: str) -> str | None:
        entry = self._peek(item_id)
        pages, titles = entry.get("page_ids") or [], entry.get("titles") or []
        return titles[pages.index(str(page_id))] if str(page_id) in pages else None

    # --- 기록 (수집 · 색인을 마친 뒤에만 부른다) ---

    def _update(self, item_id: str, change: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._refresh()
            entry = self._entry(item_id)
            change(entry)
            entry["collected_at"] = self.today().isoformat()
            self._write()

    def record_question(self, item_id: str, question: str, queries: list[str]) -> None:
        def change(entry: dict[str, Any]) -> None:
            entry["questions"][normalize_key(question)] = list(queries)

        self._update(item_id, change)

    def record_keyword(self, item_id: str, query: str) -> None:
        def change(entry: dict[str, Any]) -> None:
            if normalize_key(query) not in {normalize_key(k) for k in entry["keywords"]}:
                entry["keywords"].append(query)

        self._update(item_id, change)

    def record_item_doc(self, item_id: str, page_id: str) -> None:
        def change(entry: dict[str, Any]) -> None:
            entry["item_doc_page_id"] = str(page_id)

        self._update(item_id, change)

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> None:
        page_id = str(page_id)

        def change(entry: dict[str, Any]) -> None:
            if rejected:
                if page_id not in entry["rejected_page_ids"]:
                    entry["rejected_page_ids"].append(page_id)
            elif page_id not in entry["page_ids"]:
                entry["page_ids"].append(page_id)
                entry["titles"].append(title)
                entry["chunks"] = int(entry.get("chunks") or 0) + int(chunks)

        self._update(item_id, change)

    def reset(self, item_id: str | None = None) -> None:
        with self._lock:
            self._refresh()
            if item_id is None:
                self._data = {}
            else:
                self._data.pop(str(item_id), None)
            self._write()
