"""수집 매니페스트(캐시) — 이미 수집한 질문 · 검색어 · 문서를 영화별로 기록한다 (SPEC-NF2002).

제공 `wiki_manifest.json`과 호환되는 형식(`keywords` · `titles` · `page_ids` · `chunks` ·
`collected_at`)에 `questions` · `rejected_page_ids` · `item_doc_page_id`를 더한다.

여러 인스턴스 · 프로세스(앱과 `--reset-cache` 스크립트 등)가 같은 파일을 쓴다 (#33):
- 파일을 바꾸는 일(기록 · 초기화 · 백업)은 OS 파일 잠금(`FileLock`) 안에서,
  파일을 항상 다시 읽은 뒤 한다.
- 조회는 잠금 없이, 파일 서명(파일 ID · 수정 시각 · 크기)이 바뀌었을 때만 다시 읽는다.
- 쓰기는 고유한 임시 파일에 쓴 뒤 바꿔 넣는다.
- 깨졌거나 구조가 틀린 파일은 백업해 두고 새로 시작한다. 백업하지 못하면 덮어쓰지 않는다.
- 일시적인 파일 오류는 몇 번 다시 시도하고, 그래도 안 되면 기록을 건너뛴다
  (캐시는 성능용이라 수집을 실패시키지 않는다).
잠금 · 재시도 수치는 `settings.cache`(A-24)에서 container가 넘긴다.
`NullManifest`는 아무것도 기억하지 않는다.
"""

from __future__ import annotations

import errno
import itertools
import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from movielab.core.text import normalize_key

logger = logging.getLogger(__name__)

Signature = tuple[int, int, int]
# stat을 못 읽어 서명을 알 수 없음 — '파일 없음'(None)과 구분하고, 조회할 때마다 다시 읽는다
_UNKNOWN: Any = object()

# 다른 쪽이 잠금을 쥐고 있을 때 나는 오류 — 이때만 기다린다. 그 밖(ENOLCK 등)은 바로 포기한다.
_CONTENDED = {errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK}

if os.name == "nt":
    import msvcrt

    def _lock_fd(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _unlock_fd(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:
    import fcntl

    def _lock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_fd(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class FileLock:
    """프로세스 사이 배타 잠금 (Windows `msvcrt.locking`, 그 밖 `fcntl.flock`).

    프로세스가 죽으면 OS가 잠금을 풀어 주므로 '오래된 잠금' 판단이 없고, 잠금 파일은 지우지 않는다.
    같은 프로세스 안에서도 핸들(객체)마다 따로 잠근다.
    """

    def __init__(
        self,
        path: Path,
        *,
        poll_sec: float,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.path = Path(path)
        self.poll_sec = poll_sec
        self.clock = clock
        self.sleep = sleep
        self._fd: int | None = None

    def acquire(self, timeout_sec: float = 0.0) -> bool:
        """잠금을 잡으면 True.

        다른 쪽이 쥐고 있으면 `timeout_sec`까지 기다린다. 잠금 파일을 열 수 없거나
        파일 시스템이 잠금을 지원하지 않으면 기다리지 않고 False.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
        except OSError as exc:
            logger.warning("매니페스트 잠금 파일을 열 수 없다: %s", exc)
            return False
        deadline = self.clock() + timeout_sec
        while True:
            try:
                _lock_fd(fd)
            except OSError as exc:
                if exc.errno not in _CONTENDED:
                    logger.warning("매니페스트 잠금을 쓸 수 없다: %s", exc)
                    os.close(fd)
                    return False
                if self.clock() >= deadline:
                    os.close(fd)
                    return False
                self.sleep(self.poll_sec)
                continue
            self._fd = fd
            return True

    def release(self) -> None:
        if self._fd is None:
            return
        fd, self._fd = self._fd, None
        try:
            _unlock_fd(fd)
        except OSError:
            pass  # 닫으면 OS가 푼다
        finally:
            os.close(fd)


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

    def record_question(self, item_id: str, question: str, queries: list[str]) -> bool:
        return True

    def record_keyword(self, item_id: str, query: str) -> bool:
        return True

    def record_item_doc(self, item_id: str, page_id: str) -> bool:
        return True

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> bool:
        return True

    def record_collection(
        self,
        item_id: str,
        *,
        pages: Iterable[tuple[str, str, int]] = (),
        item_doc_page_id: str | None = None,
        keywords: Iterable[str] = (),
        question: tuple[str, list[str]] | None = None,
    ) -> bool:
        return True

    def reset(self, item_id: str | None = None) -> bool:
        return True


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
        lock_timeout_sec: float,
        lock_poll_sec: float,
        io_retries: int,
        io_retry_wait_sec: float,
        today: Callable[[], date] = date.today,
        now: Callable[[], datetime] = datetime.now,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """수치는 `settings.cache`(A-24)에서 받는다 — 기본값을 두지 않는다."""
        self.path = Path(path)
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")
        self.lock_timeout_sec = lock_timeout_sec
        self.lock_poll_sec = lock_poll_sec
        self.io_retries = io_retries
        self.io_retry_wait_sec = io_retry_wait_sec
        self.today = today
        self.now = now
        self.clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()  # 인스턴스 안의 `_data` 보호 — 파일 잠금을 잡은 뒤에만 쥔다
        self._signature: Signature | None = None
        self._valid_cache = False  # False면 서명과 상관없이 다음 조회에서 다시 읽는다
        self._data: dict[str, dict[str, Any]] = {}
        self._peek_all()

    # --- 파일 ---

    @staticmethod
    def _signature_of(path: Path) -> Any:
        """수정 시각만 보면 같은 타이머 틱 안의 두 쓰기를 놓친다 — 파일 ID · 크기도 본다.

        파일이 없으면 None, stat을 못 읽으면(접근 거부 등) `_UNKNOWN`.
        """
        try:
            stat = path.stat()
        except FileNotFoundError:
            return None
        except OSError:
            return _UNKNOWN
        return (stat.st_ino, stat.st_mtime_ns, stat.st_size)

    def _file_lock(self) -> FileLock:
        return FileLock(
            self.lock_path, poll_sec=self.lock_poll_sec, clock=self.clock, sleep=self.sleep
        )

    def _load(self) -> tuple[str, Any]:
        """`("ok", 내용)` · `("missing", None)` · `("broken", 사유)`.

        일시 오류가 `io_retries`번 다시 해도 계속되면 OSError.
        """
        text = ""
        for attempt in range(self.io_retries + 1):
            try:
                text = self.path.read_text(encoding="utf-8")
                break
            except FileNotFoundError:
                return "missing", None
            except UnicodeDecodeError as exc:
                return "broken", f"UTF-8이 아님: {exc}"
            except OSError:
                if attempt == self.io_retries:
                    raise
                self.sleep(self.io_retry_wait_sec)
        try:
            data = json.loads(text)
        except ValueError as exc:
            return "broken", f"읽기 실패: {exc}"
        if not _valid(data):
            return "broken", "구조가 맞지 않음"
        return "ok", data

    def _remember(self, status: str, value: Any, signature: Any) -> None:
        """읽은 결과를 메모리에 둔다. 깨졌거나 없으면 빈 매니페스트."""
        self._data = value if status == "ok" else {}
        self._signature = signature
        self._valid_cache = True

    def _backup(self, reason: str) -> bool:
        """깨진 파일을 옮겨 둔다(파일 잠금 안에서만). 옮기지 못하면 False — 덮어쓰지 않게."""
        stamp = f"{self.now():%Y%m%d%H%M%S%f}-{next(self._backup_counter)}"
        backup = self.path.with_name(f"{self.path.name}.broken-{stamp}")
        try:
            os.replace(self.path, backup)
        except FileNotFoundError:
            return True  # 그 사이 다른 쪽이 지웠다
        except OSError as exc:
            logger.warning("깨진 매니페스트를 옮기지 못했다: %s", exc)
            return False
        logger.warning("매니페스트를 %s로 옮기고 새로 시작한다 (%s)", backup.name, reason)
        return True

    def _refresh(self) -> bool:
        """조회용(잠금 없음): 파일이 바뀌었으면 다시 읽는다. 반환: 깨진 파일을 새로 봤는지.

        읽기에 실패하거나 깨졌으면 그 서명을 기억해, 파일이 다시 바뀔 때까지 재시도하지 않는다.
        읽기에 실패하면 옛 내용을 믿지 않고 빈 매니페스트로 둔다 (다른 쪽의 초기화를 놓치지 않게).
        """
        signature = self._signature_of(self.path)
        if self._valid_cache and signature is not _UNKNOWN and signature == self._signature:
            return False
        try:
            status, value = self._load()
        except OSError as exc:
            logger.warning("매니페스트를 읽지 못해 이번에는 캐시 없이 동작한다: %s", exc)
            self._remember("missing", None, signature)
            return False
        self._remember(status, value, signature)
        return status == "broken"

    def _backup_if_still_broken(self) -> None:
        """잠금을 기다리지 않고 한 번 잡아 보고, 다시 읽어도 깨져 있을 때만 백업한다.

        그 사이 다른 프로세스가 정상 파일을 썼으면 두고 간다. 못 잡으면 다음 기록 때 처리한다.
        """
        lock = self._file_lock()
        if not lock.acquire(0.0):
            return
        try:
            status, reason = self._load()
            if status == "broken":
                self._backup(reason)
        except OSError as exc:
            logger.warning("매니페스트를 읽지 못해 백업을 미룬다: %s", exc)
        finally:
            lock.release()

    def _write(self) -> bool:
        """임시 파일에 쓰고 바꿔 넣는다. 실패하면 임시 파일을 지우고 False."""
        tmp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
            signature = self._signature_of(tmp)  # 바꿔 넣기 전에 — 남의 쓰기 서명과 섞이지 않게
            for attempt in range(self.io_retries + 1):
                try:
                    os.replace(tmp, self.path)
                    self._signature = signature
                    return True
                except PermissionError:  # Windows: 다른 프로세스가 읽는 중
                    if attempt == self.io_retries:
                        raise
                    self.sleep(self.io_retry_wait_sec)
        except OSError as exc:
            logger.warning("매니페스트를 쓰지 못해 이번 기록을 건너뛴다: %s", exc)
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
        return False

    def _locked_update(self, change: Callable[[], None]) -> bool:
        """파일 잠금 안에서 다시 읽고 → 고치고 → 쓴다. 반환: 기록했는지.

        잠금 · 읽기 · 백업 · 쓰기에 실패하면 기록을 건너뛴다. 쓰기에 실패하면 메모리를 무효로
        표시해 다음 조회가 파일에서 다시 읽게 한다 (저장 안 된 기록이 캐시 적중으로 보이지 않게).
        """
        lock = self._file_lock()
        if not lock.acquire(self.lock_timeout_sec):
            logger.warning("매니페스트 잠금을 잡지 못해 이번 기록을 건너뛴다: %s", self.lock_path)
            return False
        try:
            with self._lock:
                signature = self._signature_of(self.path)
                try:
                    status, value = self._load()
                except OSError as exc:
                    logger.warning("매니페스트를 읽지 못해 이번 기록을 건너뛴다: %s", exc)
                    return False
                if status == "broken" and not self._backup(value):
                    return False
                self._remember(status, value, signature)
                try:
                    change()
                except Exception:
                    logger.exception("매니페스트 기록 내용을 만들지 못해 건너뛴다")
                    self._valid_cache = False
                    return False
                if self._write():
                    return True
                self._valid_cache = False
                return False
        finally:
            lock.release()

    def _entry(self, item_id: str) -> dict[str, Any]:
        entry = self._data.setdefault(str(item_id), _empty_entry())
        for key, value in _empty_entry().items():
            entry.setdefault(key, value)
        return entry

    def _peek_all(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            broken = self._refresh()
            data = self._data
        if broken:
            self._backup_if_still_broken()
        return data

    def _peek(self, item_id: str) -> dict[str, Any]:
        return self._peek_all().get(str(item_id)) or {}

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

    def _update(self, item_id: str, change: Callable[[dict[str, Any]], None]) -> bool:
        def apply() -> None:
            entry = self._entry(item_id)
            change(entry)
            entry["collected_at"] = self.today().isoformat()

        return self._locked_update(apply)

    def record_question(self, item_id: str, question: str, queries: list[str]) -> bool:
        def change(entry: dict[str, Any]) -> None:
            entry["questions"][normalize_key(question)] = list(queries)

        return self._update(item_id, change)

    def record_keyword(self, item_id: str, query: str) -> bool:
        def change(entry: dict[str, Any]) -> None:
            if normalize_key(query) not in {normalize_key(k) for k in entry["keywords"]}:
                entry["keywords"].append(query)

        return self._update(item_id, change)

    def record_item_doc(self, item_id: str, page_id: str) -> bool:
        def change(entry: dict[str, Any]) -> None:
            entry["item_doc_page_id"] = str(page_id)

        return self._update(item_id, change)

    def record_page(
        self, item_id: str, page_id: str, title: str, chunks: int, *, rejected: bool = False
    ) -> bool:
        page_id = str(page_id)

        def change(entry: dict[str, Any]) -> None:
            if rejected:
                if page_id not in entry["rejected_page_ids"]:
                    entry["rejected_page_ids"].append(page_id)
            elif page_id not in entry["page_ids"]:
                entry["page_ids"].append(page_id)
                entry["titles"].append(title)
                entry["chunks"] = int(entry.get("chunks") or 0) + int(chunks)

        return self._update(item_id, change)

    def record_collection(
        self,
        item_id: str,
        *,
        pages: Iterable[tuple[str, str, int]] = (),
        item_doc_page_id: str | None = None,
        keywords: Iterable[str] = (),
        question: tuple[str, list[str]] | None = None,
    ) -> bool:
        """수집 한 번의 결과를 한 번에 기록한다 — 잠금 · 쓰기 한 번, 전부 기록되거나 하나도 안 된다.

        `pages`는 `(page_id, 제목, 청크 수)`, `question`은 `(질문, 검색어 목록)`.
        """
        pages, keywords = list(pages), list(keywords)

        def change(entry: dict[str, Any]) -> None:
            for page_id, title, chunks in pages:
                if str(page_id) not in entry["page_ids"]:
                    entry["page_ids"].append(str(page_id))
                    entry["titles"].append(title)
                    entry["chunks"] = int(entry.get("chunks") or 0) + int(chunks)
            if item_doc_page_id is not None:
                entry["item_doc_page_id"] = str(item_doc_page_id)
            known = {normalize_key(k) for k in entry["keywords"]}
            for query in keywords:
                if normalize_key(query) not in known:
                    entry["keywords"].append(query)
                    known.add(normalize_key(query))
            if question is not None:
                entry["questions"][normalize_key(question[0])] = list(question[1])

        return self._update(item_id, change)

    def reset(self, item_id: str | None = None) -> bool:
        """캐시를 지운다. 반환: 지웠는지 (잠금 · 읽기 · 쓰기 실패면 False)."""

        def apply() -> None:
            if item_id is None:
                self._data = {}
            else:
                self._data.pop(str(item_id), None)

        return self._locked_update(apply)
