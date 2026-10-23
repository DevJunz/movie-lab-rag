"""한국어 위키백과 API 접근 (SPEC-NF2006 외부 API 예절).

- User-Agent에 앱 이름 · 버전 · 저장소 URL · 연락처를 넣는다 (Wikimedia User-Agent 정책).
- 요청은 프로세스 전체에서 직렬로 보내고, 이전 요청 시작 후 `min_interval_sec`만큼 간격을 둔다
  (재시도 포함). 잠금과 마지막 요청 시각은 API 주소별 공용 `RequestThrottle`이 가진다.
- 요청 예외 · 429 · 5xx · JSON이 아닌 200 · maxlag는 지수 백오프로 재시도하고, 유효한
  `Retry-After`를 따른다. 끝내 실패하면 `ExternalSourceUnavailableError`로 알린다.
- 연락처가 없으면 요청을 보내지 않는다.
"""

from __future__ import annotations

import email.utils
import logging
import math
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import requests

from movielab.core.errors import ExternalSourceUnavailableError

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}


class RequestThrottle:
    """직렬화 잠금 + 최소 호출 간격. 같은 API를 쓰는 모든 클라이언트가 하나를 공유한다."""

    def __init__(
        self,
        min_interval_sec: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval_sec = float(min_interval_sec)
        self.clock = clock
        self.sleep = sleep
        self.lock = threading.Lock()
        self._last_start: float | None = None

    def wait_interval(self) -> None:
        """잠금을 잡은 상태에서 부른다 — 재시도 전에도 간격을 지킨다."""
        if self._last_start is not None:
            remaining = self.min_interval_sec - (self.clock() - self._last_start)
            if remaining > 0:
                self.sleep(remaining)
        self._last_start = self.clock()


_SHARED: dict[str, RequestThrottle] = {}
_SHARED_LOCK = threading.Lock()


def shared_throttle(api_url: str, min_interval_sec: float) -> RequestThrottle:
    """API 주소별 프로세스 공용 throttle (Streamlit 세션 · 스레드가 여러 개여도 한 줄로)."""
    with _SHARED_LOCK:
        if api_url not in _SHARED:
            _SHARED[api_url] = RequestThrottle(min_interval_sec)
        return _SHARED[api_url]


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after


def parse_retry_after(value: Any, cap: float) -> float | None:
    """초 또는 HTTP 날짜. 음수 · NaN · 무한대 · 해석 불가면 None (백오프를 쓴다)."""
    if value is None:
        return None
    text = str(value).strip()
    try:
        seconds = float(text)
    except ValueError:
        try:
            when = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if not math.isfinite(seconds) or seconds < 0:
        return None
    return min(seconds, cap)


class WikiHttpClient:
    def __init__(
        self,
        settings: Any,
        contact: str | None,
        *,
        session: Any,
        throttle: RequestThrottle | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self.contact = (contact or "").strip()
        self.session = session
        self.clock = clock
        self.sleep = sleep
        self.throttle = throttle or RequestThrottle(
            settings.wiki.min_interval_sec, clock=clock, sleep=sleep
        )

    @property
    def user_agent(self) -> str:
        wiki = self.settings.wiki
        return (
            f"{wiki.app_name}/{wiki.app_version} "
            f"(+{wiki.project_url}; contact: {self.contact}) "
            f"python-requests/{requests.__version__}"
        )

    def _attempt(self, params: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """요청 1회. 반환: (로그용 상태, 데이터). 재시도 대상이면 _Retryable."""
        wiki = self.settings.wiki
        cap = float(wiki.max_retry_after_sec)
        try:
            response = self.session.get(
                wiki.api_url,
                params=params,
                headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"},
                timeout=wiki.timeout_sec,
            )
        except requests.RequestException as exc:
            raise _Retryable(type(exc).__name__) from exc
        status = response.status_code
        retry_after = parse_retry_after((response.headers or {}).get("Retry-After"), cap)
        if status in RETRY_STATUS:
            raise _Retryable(f"HTTP {status}", retry_after)
        if status == 404:
            return "404", {}
        if status >= 400:
            raise ExternalSourceUnavailableError(f"위키백과 API 거부: HTTP {status}")
        try:
            data = response.json()
        except ValueError as exc:  # 점검 페이지 등 JSON이 아닌 200
            raise _Retryable("HTTP 200 (JSON 아님)") from exc
        error = data.get("error") if isinstance(data, dict) else None
        if error:
            code = error.get("code")
            if code == "maxlag":
                raise _Retryable("maxlag", retry_after)
            raise ExternalSourceUnavailableError(f"위키백과 API 오류: {code}")
        return str(status), data if isinstance(data, dict) else {}

    def get(self, params: dict[str, Any]) -> dict[str, Any]:
        """공통 파라미터(format · formatversion · maxlag)를 더해 요청한다."""
        if not self.contact:
            raise ExternalSourceUnavailableError(
                "WIKI_CONTACT가 없어 위키백과 API를 호출하지 않는다"
            )
        wiki = self.settings.wiki
        full = {**params, "format": "json", "formatversion": 2, "maxlag": wiki.maxlag}
        action = params.get("action")
        attempts = int(wiki.max_retries) + 1
        with self.throttle.lock:
            for attempt in range(1, attempts + 1):
                self.throttle.wait_interval()
                started = self.clock()
                try:
                    status, data = self._attempt(full)
                except _Retryable as retry:
                    logger.info(
                        "위키 %s %s (%.2f초, 시도 %d/%d)",
                        action, retry, self.clock() - started, attempt, attempts,
                    )  # fmt: skip
                    if attempt == attempts:
                        raise ExternalSourceUnavailableError(f"재시도 소진: {retry}") from retry
                    wait = retry.retry_after
                    if wait is None:
                        wait = float(wiki.backoff_base_sec) * (2 ** (attempt - 1))
                    self.sleep(wait)
                    continue
                except ExternalSourceUnavailableError as error:
                    logger.info(
                        "위키 %s 실패: %s (%.2f초, 시도 %d)",
                        action, error, self.clock() - started, attempt,
                    )  # fmt: skip
                    raise
                logger.info(
                    "위키 %s %s (%.2f초, 시도 %d)", action, status, self.clock() - started, attempt
                )
                return data
        raise AssertionError("도달하지 않는다")  # attempts >= 1이므로 루프 안에서 끝난다
