"""수집 매니페스트(캐시) — 이미 수집한 질문 · 검색어 · 문서를 영화별로 기록한다 (SPEC-NF2002).

제공 `wiki_manifest.json`과 호환되는 형식(`keywords` · `titles` · `page_ids` · `chunks` ·
`collected_at`)에 `questions` · `rejected_page_ids` · `item_doc_page_id`를 더한다.

여러 인스턴스 · 프로세스(앱과 `--reset-cache` 스크립트 등)가 같은 파일을 쓴다 (#33):
- 기록(읽고-고치고-쓰기)은 잠금 파일(`O_EXCL`) 안에서, 파일을 항상 다시 읽은 뒤 한다.
- 조회는 잠금 없이, 파일 서명(파일 ID · 수정 시각 · 크기)이 바뀌었을 때만 다시 읽는다.
- 쓰기는 고유한 임시 파일에 쓴 뒤 바꿔 넣는다.
- 깨졌거나 구조가 틀린 파일은 백업해 두고 새로 시작한다.
- 일시적인 파일 오류는 몇 번 다시 시도하고, 그래도 안 되면 기록을 건너뛴다 (캐시는 성능용이다).
`NullManifest`는 아무것도 기억하지 않는다.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from movielab.core.text import normalize_key

logger = logging.getLogger(__name__)

Signature = tuple[int, int, int]

_RETRIES = 5  # 일시적인 읽기 · 바꿔 넣기 오류 재시도 횟수
_RETRY_WAIT_SEC = 0.05
_LOCK_POLL_SEC = 0.01


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
        lock_timeout_sec: float = 10.0,
        stale_lock_sec: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self.today = today
        self.now = now
        self.lock_timeout_sec = lock_timeout_sec
        self.stale_lock_sec = stale_lock_sec
        self.sleep = sleep
        self._lock = threading.Lock()
        self._signature: Signature | None = None
        self._data: dict[str, dict[str, Any]] = {}
        self._refresh()

    # --- 파일 ---

    @staticmethod
    def _signature_of(path: Path) -> Signature | None:
        """수정 시각만 보면 같은 타이머 틱 안의 두 쓰기를 놓친다 — 파일 ID · 크기도 본다."""
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        return (stat.st_ino, stat.st_mtime_ns, stat.st_size)

    def _backup(self, reason: str) -> None:
        stamp = f"{self.now():%Y%m%d%H%M%S%f}-{next(self._backup_counter)}"
        backup = self.path.with_name(f"{self.path.name}.broken-{stamp}")
        try:
            os.replace(self.path, backup)
        except FileNotFoundError:
            return  # 그 사이 다른 쪽이 지웠다
        logger.warning("매니페스트를 %s로 옮기고 새로 시작한다 (%s)", backup.name, reason)

    def _read(self) -> str | None:
        """파일 내용. 없으면 None. 일시적인 오류(공유 위반 등)가 계속되면 OSError."""
        for attempt in range(_RETRIES):
            try:
                return self.path.read_text(encoding="utf-8")
            except FileNotFoundError:
                return None
            except OSError:
                if attempt == _RETRIES - 1:
                    raise
                self.sleep(_RETRY_WAIT_SEC)
        return None

    def _refresh(self, *, force: bool = False) -> bool:
        """파일이 바뀌었으면(`force`면 항상) 다시 읽는다. 읽지 못하면 지금 내용을 두고 False."""
        signature = self._signature_of(self.path)
        if not force and signature == self._signature:
            return True
        try:
            text = self._read()
        except OSError as exc:
            logger.warning("매니페스트를 읽지 못해 지금 내용을 유지한다: %s", exc)
            return False
        if text is None:
            self._data, self._signature = {}, None
            return True
        try:
            data = json.loads(text)
        except ValueError as exc:
            self._backup(f"읽기 실패: {exc}")
            self._data, self._signature = {}, None
            return True
        if not _valid(data):
            self._backup("구조가 맞지 않음")
            self._data, self._signature = {}, None
            return True
        self._data, self._signature = data, signature
        return True

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        signature = self._signature_of(tmp)  # 바꿔 넣기 전에 — 남의 쓰기 서명과 섞이지 않게
        for attempt in range(_RETRIES):
            try:
                os.replace(tmp, self.path)
                self._signature = signature
                return
            except PermissionError:  # Windows: 다른 프로세스가 읽는 중
                if attempt < _RETRIES - 1:
                    self.sleep(_RETRY_WAIT_SEC)
        tmp.unlink(missing_ok=True)
        self._signature = None  # 다음 조회에서 파일 내용으로 돌아간다
        logger.warning("매니페스트를 바꿔 넣지 못해 이번 기록을 건너뛴다: %s", self.path)

    def _lock_is_stale(self) -> bool:
        try:
            return time.time() - self.lock_path.stat().st_mtime > self.stale_lock_sec
        except FileNotFoundError:
            return False

    def _acquire(self) -> bool:
        """프로세스 사이 잠금. 오래된 잠금은 지우고 다시 잡는다. 시간 안에 못 잡으면 False."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout_sec
        while True:
            try:
                os.close(os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
                return True
            except (FileExistsError, PermissionError):  # Windows: 지우는 중이면 PermissionError
                if self._lock_is_stale():
                    logger.warning("오래된 매니페스트 잠금을 지운다: %s", self.lock_path)
                    self.lock_path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    return False
                self.sleep(_LOCK_POLL_SEC)

    def _release(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    def _locked_update(self, change: Callable[[], None]) -> None:
        """잠금 안에서 파일을 다시 읽고 → 고치고 → 쓴다. 잠금 · 읽기에 실패하면 기록을 건너뛴다."""
        with self._lock:
            if not self._acquire():
                logger.warning(
                    "매니페스트 잠금을 잡지 못해 이번 기록을 건너뛴다: %s", self.lock_path
                )
                return
            try:
                if not self._refresh(force=True):
                    return
                change()
                self._write()
            finally:
                self._release()

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
        def apply() -> None:
            entry = self._entry(item_id)
            change(entry)
            entry["collected_at"] = self.today().isoformat()

        self._locked_update(apply)

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
        def apply() -> None:
            if item_id is None:
                self._data = {}
            else:
                self._data.pop(str(item_id), None)

        self._locked_update(apply)
