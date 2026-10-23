"""SPEC-NF2005 TC-08 — CI용 가짜 객체가 정의대로 동작한다."""

from __future__ import annotations

import math

import pytest
import requests

from tests.fakes import (
    FakeChatModel,
    FakeClock,
    FakeEmbeddings,
    FakeHttpSession,
    FakeResponse,
    task_of,
)


def test_tc_nf2005_08_fake_chat_routes_by_task_header():
    llm = FakeChatModel(
        rules={"검색어 추출": '["웜홀"]', "답변 생성": lambda p: "길이 " + str(len(p))}
    )
    assert llm.invoke("[작업: 검색어 추출]\n질문").content == '["웜홀"]'
    assert llm.invoke("[작업: 답변 생성]\nabc").content.startswith("길이 ")
    assert llm.invoke("머리표 없음").content == ""
    assert [task for task, _ in llm.calls] == ["검색어 추출", "답변 생성", None]
    assert llm.prompts_for("검색어 추출") == ["[작업: 검색어 추출]\n질문"]


def test_tc_nf2005_08_fake_chat_raises_configured_error():
    llm = FakeChatModel(rules={"후보 선별": RuntimeError("실패")})
    with pytest.raises(RuntimeError):
        llm.invoke("[작업: 후보 선별]\n")


def test_tc_nf2005_08_task_of():
    assert task_of("  [작업: 사실 판정]\n본문") == "사실 판정"
    assert task_of("본문") is None


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_tc_nf2005_08_fake_embeddings_deterministic_and_similarity_ordered():
    emb = FakeEmbeddings()
    a = emb.embed_query("블랙홀은 빛도 빠져나올 수 없는 천체이다")
    assert a == FakeEmbeddings().embed_query("블랙홀은 빛도 빠져나올 수 없는 천체이다")
    assert math.isclose(_cos(a, a), 1.0)
    near = emb.embed_query("블랙홀은 빛조차 빠져나오지 못하는 천체")
    far = emb.embed_query("조선 수군은 열두 척의 배로 싸웠다")
    assert _cos(a, near) > _cos(a, far)
    assert len(emb.embed_documents(["가", "나"])) == 2


def test_tc_nf2005_08_fake_http_session_routes_and_records():
    clock = FakeClock()
    session = FakeHttpSession(clock=clock)
    session.add({"list": "search"}, FakeResponse(status_code=503), {"ok": 1})
    session.add(lambda p: p.get("action") == "fail", requests.ConnectionError("끊김"))
    assert session.get("u", params={"list": "search"}).status_code == 503
    assert session.get("u", params={"list": "search"}).json() == {"ok": 1}
    assert session.get("u", params={"list": "search"}).json() == {"ok": 1}  # 마지막 응답 반복
    with pytest.raises(requests.ConnectionError):
        session.get("u", params={"action": "fail"})
    with pytest.raises(AssertionError):
        session.get("u", params={"action": "unknown"})
    first = session.requests[0]
    assert first["params"] == {"list": "search"} and first["at"] == clock.now
    with pytest.raises(requests.HTTPError):
        FakeResponse(status_code=429).raise_for_status()


def test_tc_nf2005_08_fake_clock():
    clock = FakeClock(start=10.0)
    clock.sleep(1.5)
    clock.advance(0.5)
    assert clock.monotonic() == 12.0
    assert clock.sleeps == [1.5]
