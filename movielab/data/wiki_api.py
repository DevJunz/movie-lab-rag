"""한국어 위키백과 API 접근 (SPEC-NF2006 외부 API 예절).

- User-Agent에 앱 이름 · 버전 · 저장소 URL · 연락처를 넣는다 (Wikimedia User-Agent 정책).
- 요청은 직렬로 보내고, 이전 요청 시작 후 `min_interval_sec`만큼 간격을 둔다 (재시도 포함).
- 429 · 5xx · 연결 오류 · maxlag는 지수 백오프로 재시도하고 `Retry-After`를 따른다.
- 연락처가 없으면 요청을 보내지 않는다.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import requests

from movielab.core.errors import ExternalSourceUnavailableError

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SEC = 60.0


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after


def _retry_after(response: Any) -> float | None:
    value = (getattr(response, "headers", None) or {}).get("Retry-After")
    try:
        return min(float(value), MAX_RETRY_AFTER_SEC) if value is not None else None
    except (TypeError, ValueError):
        return None


class WikiHttpClient:
    def __init__(
        self,
        settings: Any,
        contact: str | None,
        *,
        session: Any = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.contact = (contact or "").strip()
        self.session = session if session is not None else requests.Session()
        self.clock = clock
        self.sleep = sleep
        self._lock = threading.Lock()
        self._last_start: float | None = None

    @property
    def user_agent(self) -> str:
        wiki = self.settings.wiki
        return (
            f"{wiki.app_name}/{wiki.app_version} "
            f"(+{wiki.project_url}; contact: {self.contact}) "
            f"python-requests/{requests.__version__}"
        )

    def _wait_turn(self) -> None:
        interval = float(self.settings.wiki.min_interval_sec)
        if self._last_start is not None:
            remaining = interval - (self.clock() - self._last_start)
            if remaining > 0:
                self.sleep(remaining)
        self._last_start = self.clock()

    def _attempt(self, params: dict[str, Any]) -> dict[str, Any]:
        wiki = self.settings.wiki
        try:
            response = self.session.get(
                wiki.api_url,
                params=params,
                headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"},
                timeout=wiki.timeout_sec,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise _Retryable(f"연결 오류: {type(exc).__name__}") from exc
        status = response.status_code
        if status in RETRY_STATUS:
            raise _Retryable(f"HTTP {status}", _retry_after(response))
        if status == 404:
            return {}
        if status >= 400:
            raise ExternalSourceUnavailableError(f"위키백과 API 거부: HTTP {status}")
        data = response.json() or {}
        error = data.get("error") if isinstance(data, dict) else None
        if error:
            if error.get("code") == "maxlag":
                raise _Retryable("maxlag", _retry_after(response))
            raise ExternalSourceUnavailableError(f"위키백과 API 오류: {error.get('code')}")
        return data

    def get(self, params: dict[str, Any]) -> dict[str, Any]:
        """공통 파라미터(format · formatversion · maxlag)를 더해 요청한다."""
        if not self.contact:
            raise ExternalSourceUnavailableError(
                "WIKI_CONTACT가 없어 위키백과 API를 호출하지 않는다"
            )
        wiki = self.settings.wiki
        full = {**params, "format": "json", "formatversion": 2, "maxlag": wiki.maxlag}
        with self._lock:
            for attempt in range(int(wiki.max_retries) + 1):
                self._wait_turn()
                started = time.perf_counter()
                try:
                    data = self._attempt(full)
                except _Retryable as retry:
                    logger.info(
                        "위키 %s 재시도 대상: %s (시도 %d)",
                        params.get("action"),
                        retry,
                        attempt + 1,
                    )
                    if attempt >= int(wiki.max_retries):
                        raise ExternalSourceUnavailableError(f"재시도 소진: {retry}") from retry
                    wait = retry.retry_after
                    if wait is None:
                        wait = float(wiki.backoff_base_sec) * (2**attempt)
                    self.sleep(wait)
                    continue
                logger.info(
                    "위키 %s 완료 (%.2f초, 재시도 %d)",
                    params.get("action"),
                    time.perf_counter() - started,
                    attempt,
                )
                return data
        raise ExternalSourceUnavailableError("재시도 소진")  # 도달하지 않음
