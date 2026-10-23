"""`requests.Session`을 대신하는 가짜. 요청을 기록하고 등록한 응답을 순서대로 돌려준다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests


@dataclass
class FakeResponse:
    payload: Any = None
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        return self.payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} 오류", response=self)  # type: ignore[arg-type]


Matcher = Callable[[dict[str, Any]], bool] | dict[str, Any]


class FakeHttpSession:
    """`add(조건, 응답…)`으로 등록한다. 조건은 파라미터 부분 일치 dict 또는 함수.

    응답은 `FakeResponse`, dict(200 JSON), 또는 던질 예외. 같은 조건의 응답은 차례로 쓰고 마지막 것을 반복한다.
    """

    def __init__(self, clock: Any = None) -> None:
        self.routes: list[tuple[Matcher, list[Any]]] = []
        self.requests: list[dict[str, Any]] = []
        self.clock = clock
        self.headers: dict[str, str] = {}

    def add(self, match: Matcher, *responses: Any) -> FakeHttpSession:
        self.routes.append((match, list(responses)))
        return self

    @staticmethod
    def _matches(match: Matcher, params: dict[str, Any]) -> bool:
        if callable(match):
            return bool(match(params))
        return all(str(params.get(k)) == str(v) for k, v in match.items())

    def get(self, url: str, params: dict[str, Any] | None = None, **kwargs: Any) -> FakeResponse:
        params = dict(params or {})
        headers = {**self.headers, **(kwargs.get("headers") or {})}
        self.requests.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": kwargs.get("timeout"),
                "at": self.clock.monotonic() if self.clock else None,
            }
        )
        for match, responses in self.routes:
            if self._matches(match, params):
                item = responses.pop(0) if len(responses) > 1 else responses[0]
                if isinstance(item, BaseException):
                    raise item
                return item if isinstance(item, FakeResponse) else FakeResponse(payload=item)
        raise AssertionError(f"등록되지 않은 요청: {params}")
