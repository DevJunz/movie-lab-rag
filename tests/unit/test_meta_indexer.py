"""SPEC-F2002 TC-06 · TC-12 — 배치 재시도 규칙 (가짜 저장소)."""

from __future__ import annotations

import httpx
import openai
import pytest

from movielab.core.errors import MissingApiKeyError
from movielab.core.types import ItemRecord
from movielab.index.meta_indexer import index_items
from tests.fakes import FakeClock


class FlakyStore:
    """`errors` 목록의 예외를 차례로 던지고, 다 쓰면 성공한다."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def upsert(self, name, documents):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)


def _items(n=3):
    return [ItemRecord(str(i), f"t{i}", 2000, "x", {}, "") for i in range(n)]


def _run(store, retries=2, wait=1.5):
    clock = FakeClock()
    failed = index_items(
        store, _items(), collection="c", batch_size=10, retries=retries, retry_wait_sec=wait,
        sleep=clock.sleep,
    )  # fmt: skip
    return failed, clock


def test_tc_f2002_06_transient_error_retried_after_wait():
    store = FlakyStore([RuntimeError("일시 장애")])
    failed, clock = _run(store)
    assert failed == [] and store.calls == 2 and clock.sleeps == [1.5]


def test_tc_f2002_06_gives_up_after_retries():
    store = FlakyStore([RuntimeError("장애")] * 5)
    failed, clock = _run(store, retries=2)
    assert failed == [0] and store.calls == 3 and clock.sleeps == [1.5, 1.5]


def _auth_error():
    request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
    return openai.AuthenticationError(
        "invalid key", response=httpx.Response(401, request=request), body=None
    )


@pytest.mark.parametrize(
    "error",
    [ValueError("메타데이터 형식"), TypeError("x"), MissingApiKeyError("키 없음")],
    ids=["value", "type", "user-error"],
)
def test_tc_f2002_12_unrecoverable_errors_not_retried(error):
    store = FlakyStore([error])
    with pytest.raises(type(error)):
        _run(store)
    assert store.calls == 1


def test_tc_f2002_12_auth_error_not_retried():
    store = FlakyStore([_auth_error()])
    with pytest.raises(openai.AuthenticationError):
        _run(store)
    assert store.calls == 1


def test_tc_f2002_18_truncated_json_response_is_retried():
    import json

    store = FlakyStore([json.JSONDecodeError("잘린 응답", "{", 1)])
    failed, clock = _run(store)
    assert failed == [] and store.calls == 2 and clock.sleeps == [1.5]
