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
import html
import logging
import math
import re
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any

import requests

from movielab.core.errors import ExternalSourceUnavailableError
from movielab.core.types import Candidate, SourceDocument

logger = logging.getLogger(__name__)


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


_SHARED: dict[tuple[str, float], RequestThrottle] = {}
_SHARED_LOCK = threading.Lock()


def shared_throttle(api_url: str, min_interval_sec: float) -> RequestThrottle:
    """API 주소별 프로세스 공용 throttle (Streamlit 세션 · 스레드가 여러 개여도 한 줄로)."""
    key = (api_url, float(min_interval_sec))
    with _SHARED_LOCK:
        if key not in _SHARED:
            _SHARED[key] = RequestThrottle(min_interval_sec)
        return _SHARED[key]


def _should_retry(status: int) -> bool:
    return status == 429 or 500 <= status <= 599


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _Retryable(Exception):
    def __init__(self, reason: str, retry_after: float | None = None) -> None:
        super().__init__(reason)
        self.retry_after = retry_after


def parse_retry_after(
    value: Any, cap: float, now: Callable[[], datetime] = _utc_now
) -> float | None:
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
        seconds = (when - now()).total_seconds()
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
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.settings = settings
        self.contact = (contact or "").strip()
        self.session = session
        self.clock = clock
        self.sleep = sleep
        self.now = now
        self.throttle = throttle or RequestThrottle(
            settings.wiki.min_interval_sec, clock=clock, sleep=sleep
        )
        wiki = settings.wiki
        self.user_agent = (
            f"{wiki.app_name}/{wiki.app_version} "
            f"(+{wiki.project_url}; contact: {self.contact}) "
            f"python-requests/{requests.__version__}"
        )
        self._header_problem = self._check_header(self.user_agent)

    @staticmethod
    def _check_header(value: str) -> str | None:
        """HTTP 헤더에 쓸 수 없는 값이면 이유를 돌려준다 (latin-1 밖 문자, 줄바꿈)."""
        if any(ch in value for ch in ("\r", "\n")):
            return "줄바꿈 문자"
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            return "latin-1로 표현할 수 없는 문자"
        return None

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
        retry_after = parse_retry_after((response.headers or {}).get("Retry-After"), cap, self.now)
        if _should_retry(status):
            raise _Retryable(f"HTTP {status}", retry_after)
        if status == 404:
            return "404", {}
        if status >= 400:
            raise ExternalSourceUnavailableError(f"위키백과 API 거부: HTTP {status}")
        try:
            data = response.json()
        except ValueError as exc:  # 점검 페이지 등 JSON이 아닌 200
            raise _Retryable("HTTP 200 (JSON 아님)") from exc
        if not isinstance(data, dict):  # [] · null 등 — 정상 응답이 아니다
            raise _Retryable("HTTP 200 (JSON 객체 아님)")
        error = data.get("error")
        if error:
            code = error.get("code") if isinstance(error, dict) else str(error)
            if code == "maxlag":
                raise _Retryable("maxlag", retry_after)
            raise ExternalSourceUnavailableError(f"위키백과 API 오류: {code}")
        return str(status), data

    def get(self, params: dict[str, Any]) -> dict[str, Any]:
        """공통 파라미터(format · formatversion · maxlag)를 더해 요청한다."""
        if not self.contact:
            raise ExternalSourceUnavailableError(
                "WIKI_CONTACT가 없어 위키백과 API를 호출하지 않는다"
            )
        if self._header_problem:
            logger.warning("WIKI_CONTACT를 User-Agent에 쓸 수 없다: %s", self._header_problem)
            raise ExternalSourceUnavailableError(f"User-Agent 오류: {self._header_problem}")
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


# --- 문서 소스 (SPEC-F2004 §3.1) ---

SOURCE_NAME = "한국어 위키백과"
_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return " ".join(html.unescape(_TAG.sub("", text or "")).split())


def _is_disambiguation(page: dict[str, Any]) -> bool:
    return "disambiguation" in (page.get("pageprops") or {}) or str(page.get("title", "")).endswith(
        "(동음이의)"
    )


class WikiApiSource:
    """MediaWiki API 기반 문서 소스. 모든 요청은 WikiHttpClient(NF2006)를 거친다."""

    kind = "api"

    def __init__(self, client: WikiHttpClient, *, today: Callable[[], date] = date.today) -> None:
        self.client = client
        self.today = today

    def search(self, query: str, limit: int, item_id: str | None = None) -> list[Candidate]:
        """`list=search`(요약)와 `generator=search`(동음이의 `pageprops`)를 한 요청으로 받는다."""
        data = self.client.get(
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": limit,
                "srnamespace": 0,
                "srprop": "snippet|size",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": limit,
                "gsrnamespace": 0,
                "prop": "pageprops",
                "ppprop": "disambiguation",
            }
        )
        body = data.get("query") or {}
        disambiguation = {
            str(page.get("pageid")) for page in body.get("pages") or [] if _is_disambiguation(page)
        }
        return [
            Candidate(
                page_id=str(r["pageid"]),
                title=r["title"],
                snippet=_strip_html(r.get("snippet", "")),
                size=int(r.get("size") or 0),
                query=query,
                disambiguation=_is_disambiguation(r) or str(r["pageid"]) in disambiguation,
            )
            for r in body.get("search") or []
        ]

    def resolve_titles(self, titles: list[str]) -> list[Candidate]:
        """제목 직접 조회. 넘겨주기를 따라가고, 요청한 제목(`matched_title`) 순서로 돌려준다."""
        data = self.client.get(
            {
                "action": "query",
                "titles": "|".join(titles),
                "redirects": 1,
                "prop": "info|pageprops|extracts",
                "ppprop": "disambiguation",
                "inprop": "url",
                "exintro": 1,
                "explaintext": 1,
                "exchars": int(self.client.settings.collect.intro_chars),
                "exlimit": len(titles),
            }
        )
        query = data.get("query") or {}
        rename = {n["from"]: n["to"] for n in query.get("normalized") or []}
        redirect = {r["from"]: r["to"] for r in query.get("redirects") or []}
        pages = {p["title"]: p for p in query.get("pages") or [] if not p.get("missing")}
        found: list[Candidate] = []
        for requested in titles:
            title = rename.get(requested, requested)
            title = redirect.get(title, title)
            page = pages.get(title)
            if page is None or "pageid" not in page:
                continue
            found.append(
                Candidate(
                    page_id=str(page["pageid"]),
                    title=page["title"],
                    snippet=page.get("extract") or "",
                    url=page.get("fullurl", ""),
                    matched_title=requested,
                    disambiguation=_is_disambiguation(page),
                )
            )
        return found

    def fetch(self, page_id: str) -> SourceDocument | None:
        data = self.client.get(
            {
                "action": "query",
                "pageids": page_id,
                "prop": "extracts|info",
                "explaintext": 1,
                "inprop": "url",
            }
        )
        pages = (data.get("query") or {}).get("pages") or []
        if not pages or pages[0].get("missing") or "pageid" not in pages[0]:
            return None
        page = pages[0]
        return SourceDocument(
            page_id=str(page["pageid"]),
            title=page["title"],
            url=page.get("fullurl", ""),
            text=page.get("extract") or "",
            source=SOURCE_NAME,
            movie_id="",
            related_movie="",
            search_query="",
            collected_at=self.today().isoformat(),
        )
