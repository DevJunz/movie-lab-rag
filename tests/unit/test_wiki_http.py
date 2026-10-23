"""SPEC-NF2006 외부 API 예절 — User-Agent, 호출 간격, 재시도, maxlag, 직렬 요청."""

from __future__ import annotations

import email.utils
import logging
import time

import pytest
import requests

from movielab.core.errors import ExternalSourceUnavailableError
from movielab.data.wiki_api import RequestThrottle, WikiHttpClient
from tests.fakes import FakeClock, FakeHttpSession, FakeResponse

CONTACT = "tester@example.invalid"
OK = {"query": {"search": []}}


def _throttle(settings, clock):
    return RequestThrottle(settings.wiki.min_interval_sec, clock=clock.monotonic, sleep=clock.sleep)


def _client(settings, session, clock=None, contact=CONTACT, throttle=None):
    clock = clock or FakeClock()
    session.clock = clock
    throttle = throttle or _throttle(settings, clock)
    client = WikiHttpClient(
        settings, contact, session=session, throttle=throttle, clock=clock.monotonic,
        sleep=clock.sleep,
    )  # fmt: skip
    return client, clock


def test_tc_nf2006_01_user_agent_has_app_version_and_contact(tmp_settings):
    session = FakeHttpSession().add({}, OK)
    client, _ = _client(tmp_settings, session)
    client.get({"action": "query", "list": "search", "srsearch": "블랙홀"})
    headers = session.requests[0]["headers"]
    ua = headers["User-Agent"]
    assert ua.startswith("MovieLab/0.1 (")
    assert CONTACT in ua and "https://github.com/DevJunz/movie-lab-rag" in ua
    assert "python-requests/" in ua
    assert "gzip" in headers.get("Accept-Encoding", "")
    assert session.requests[0]["timeout"] == 10


@pytest.mark.parametrize("contact", [None, "", "   "])
def test_tc_nf2006_02_no_contact_no_request(tmp_settings, contact):
    session = FakeHttpSession().add({}, OK)
    client, _ = _client(tmp_settings, session, contact=contact)
    with pytest.raises(ExternalSourceUnavailableError) as error:
        client.get({"action": "query"})
    assert error.value.code == "SOURCE_UNAVAILABLE"
    assert session.requests == []


def test_tc_nf2006_03_min_interval_between_requests(tmp_settings):
    session = FakeHttpSession().add({}, OK)
    client, clock = _client(tmp_settings, session)
    for _ in range(3):
        client.get({"action": "query"})
    starts = [r["at"] for r in session.requests]
    assert all(b - a >= 1.0 for a, b in zip(starts, starts[1:], strict=False))
    assert clock.sleeps == [1.0, 1.0]


def test_tc_nf2006_03_no_wait_if_enough_time_passed(tmp_settings):
    session = FakeHttpSession().add({}, OK)
    client, clock = _client(tmp_settings, session)
    client.get({"action": "query"})
    clock.advance(5)
    client.get({"action": "query"})
    assert clock.sleeps == []


def test_tc_nf2006_04_retry_with_exponential_backoff(tmp_settings):
    session = FakeHttpSession().add(
        {}, FakeResponse(status_code=503), FakeResponse(status_code=503), OK
    )
    client, clock = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == OK
    assert len(session.requests) == 3
    assert clock.sleeps == [1.0, 2.0]


def test_tc_nf2006_04_connection_error_retried(tmp_settings):
    session = FakeHttpSession().add({}, requests.ConnectionError("끊김"), requests.Timeout(), OK)
    client, clock = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == OK
    assert len(session.requests) == 3


def test_tc_nf2006_05_retry_after_header_respected(tmp_settings):
    session = FakeHttpSession().add(
        {}, FakeResponse(status_code=429, headers={"Retry-After": "7"}), OK
    )
    client, clock = _client(tmp_settings, session)
    client.get({"action": "query"})
    assert clock.sleeps == [7.0]


def test_tc_nf2006_05_retry_after_capped_at_60(tmp_settings):
    session = FakeHttpSession().add(
        {}, FakeResponse(status_code=429, headers={"Retry-After": "3600"}), OK
    )
    client, clock = _client(tmp_settings, session)
    client.get({"action": "query"})
    assert clock.sleeps == [60.0]


def test_tc_nf2006_06_gives_up_after_max_retries(tmp_settings):
    session = FakeHttpSession().add({}, FakeResponse(status_code=503))
    client, clock = _client(tmp_settings, session)
    with pytest.raises(ExternalSourceUnavailableError):
        client.get({"action": "query"})
    assert len(session.requests) == 4  # 첫 시도 + 재시도 3회
    assert clock.sleeps == [1.0, 2.0, 4.0]


def test_tc_nf2006_07_forbidden_not_retried(tmp_settings):
    session = FakeHttpSession().add({}, FakeResponse(status_code=403))
    client, clock = _client(tmp_settings, session)
    with pytest.raises(ExternalSourceUnavailableError):
        client.get({"action": "query"})
    assert len(session.requests) == 1 and clock.sleeps == []


def test_tc_nf2006_07_not_found_returns_empty(tmp_settings):
    session = FakeHttpSession().add({}, FakeResponse(status_code=404))
    client, _ = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == {}
    assert len(session.requests) == 1


def test_tc_nf2006_08_common_params_added(tmp_settings):
    session = FakeHttpSession().add({}, OK)
    client, _ = _client(tmp_settings, session)
    client.get({"action": "query", "list": "search"})
    params = session.requests[0]["params"]
    assert params["maxlag"] == 5
    assert params["format"] == "json"
    assert params["formatversion"] == 2
    assert params["action"] == "query" and params["list"] == "search"
    assert session.requests[0]["url"] == "https://ko.wikipedia.org/w/api.php"


def test_tc_nf2006_09_maxlag_error_body_retried(tmp_settings):
    lagged = {"error": {"code": "maxlag", "info": "Waiting for a database server"}}
    session = FakeHttpSession().add({}, lagged, OK)
    client, clock = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == OK
    assert len(session.requests) == 2 and clock.sleeps == [1.0]


def test_tc_nf2006_09_other_api_error_raises(tmp_settings):
    session = FakeHttpSession().add({}, {"error": {"code": "badparams", "info": "x"}})
    client, _ = _client(tmp_settings, session)
    with pytest.raises(ExternalSourceUnavailableError):
        client.get({"action": "query"})
    assert len(session.requests) == 1


def test_tc_nf2006_10_shared_lock_held_during_every_request(tmp_settings):
    held = []
    throttle_box = {}
    session = FakeHttpSession(on_get=lambda params: held.append(throttle_box["t"].lock.locked()))
    session.add({}, FakeResponse(status_code=503), OK)
    clock = FakeClock()
    throttle_box["t"] = _throttle(tmp_settings, clock)
    client, _ = _client(tmp_settings, session, clock=clock, throttle=throttle_box["t"])
    client.get({"action": "query"})
    client.get({"action": "query"})
    assert held == [True, True, True]
    assert not throttle_box["t"].lock.locked()


def test_tc_nf2006_12_non_json_200_retried_then_unavailable(tmp_settings):
    class HtmlResponse(FakeResponse):
        def json(self):
            raise ValueError("Expecting value")  # requests.JSONDecodeError의 상위

    session = FakeHttpSession().add({}, HtmlResponse(payload="<html>점검 중</html>"))
    client, clock = _client(tmp_settings, session)
    with pytest.raises(ExternalSourceUnavailableError):
        client.get({"action": "query"})
    assert len(session.requests) == 4

    session = FakeHttpSession().add({}, HtmlResponse(payload="<html/>"), OK)
    client, _ = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == OK


@pytest.mark.parametrize(
    "error",
    [requests.exceptions.ChunkedEncodingError("끊김"), requests.exceptions.ContentDecodingError()],
)
def test_tc_nf2006_13_body_errors_retried(tmp_settings, error):
    session = FakeHttpSession().add({}, error, OK)
    client, _ = _client(tmp_settings, session)
    assert client.get({"action": "query"}) == OK
    assert len(session.requests) == 2


def test_tc_nf2006_14_retry_after_http_date(tmp_settings, monkeypatch):
    when = email.utils.formatdate(time.time() + 10, usegmt=True)
    session = FakeHttpSession().add(
        {}, FakeResponse(status_code=503, headers={"Retry-After": when}), OK
    )
    client, clock = _client(tmp_settings, session)
    client.get({"action": "query"})
    assert len(clock.sleeps) == 1 and 8.0 <= clock.sleeps[0] <= 10.5


@pytest.mark.parametrize("value", ["-5", "nan", "abc", "inf"])
def test_tc_nf2006_14_invalid_retry_after_uses_backoff(tmp_settings, value):
    session = FakeHttpSession().add(
        {}, FakeResponse(status_code=429, headers={"Retry-After": value}), OK
    )
    client, clock = _client(tmp_settings, session)
    client.get({"action": "query"})
    assert clock.sleeps == [1.0]


def test_tc_nf2006_15_two_clients_share_throttle(tmp_settings):
    clock = FakeClock()
    shared = _throttle(tmp_settings, clock)
    first, _ = _client(tmp_settings, FakeHttpSession().add({}, OK), clock=clock, throttle=shared)
    second, _ = _client(tmp_settings, FakeHttpSession().add({}, OK), clock=clock, throttle=shared)
    first.get({"action": "query"})
    second.get({"action": "query"})
    assert clock.sleeps == [1.0]


def test_tc_nf2006_15_container_uses_process_wide_throttle(tmp_settings, monkeypatch):
    from movielab.config import load_settings
    from movielab.container import build_services

    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setenv("WIKI_CONTACT", CONTACT)
    a = build_services(load_settings(), http=FakeHttpSession()).wiki_client
    b = build_services(load_settings(), http=FakeHttpSession()).wiki_client
    assert a is not b and a.throttle is b.throttle


def test_tc_nf2006_16_every_request_logged_with_status(tmp_settings, caplog):
    session = FakeHttpSession()
    session.add({"list": "ok"}, OK)
    session.add({"list": "denied"}, FakeResponse(status_code=403))
    session.add({"list": "bad"}, {"error": {"code": "badparams"}})
    client, _ = _client(tmp_settings, session)
    with caplog.at_level(logging.INFO, logger="movielab.data.wiki_api"):
        client.get({"action": "query", "list": "ok"})
        for kind in ("denied", "bad"):
            with pytest.raises(ExternalSourceUnavailableError):
                client.get({"action": "query", "list": kind})
    text = caplog.text
    assert "200" in text and "403" in text and "badparams" in text
    assert CONTACT not in text


def test_tc_nf2006_01_container_wires_wiki_client(tmp_settings, monkeypatch):
    from movielab.config import load_settings
    from movielab.container import build_services

    session = FakeHttpSession().add({}, OK)
    services = build_services(tmp_settings, http=session)
    with pytest.raises(ExternalSourceUnavailableError):  # tmp_settings에는 연락처가 없다
        services.wiki_client.get({"action": "query"})
    assert session.requests == []

    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    monkeypatch.setenv("WIKI_CONTACT", CONTACT)
    services = build_services(load_settings(), http=session)
    assert services.wiki_client is services.wiki_client
    assert CONTACT in services.wiki_client.user_agent
    assert services.wiki_client.session is session


def test_tc_nf2006_01_session_required():
    with pytest.raises(TypeError):
        WikiHttpClient(None, CONTACT)  # 세션은 container가 만들어 넘긴다
