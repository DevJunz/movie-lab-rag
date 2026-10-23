"""SPEC-NF2006 외부 API 예절 — User-Agent, 호출 간격, 재시도, maxlag, 직렬 요청."""

from __future__ import annotations

import threading
import time

import pytest
import requests

from movielab.core.errors import ExternalSourceUnavailableError
from movielab.data.wiki_api import WikiHttpClient
from tests.fakes import FakeClock, FakeHttpSession, FakeResponse

CONTACT = "tester@example.invalid"
OK = {"query": {"search": []}}


def _client(settings, session, clock=None, contact=CONTACT):
    clock = clock or FakeClock()
    session.clock = clock
    return WikiHttpClient(
        settings, contact, session=session, clock=clock.monotonic, sleep=clock.sleep
    ), clock


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


def test_tc_nf2006_10_requests_are_serialized(tmp_settings):
    tmp_settings.raw["wiki"]["min_interval_sec"] = 0

    class SlowSession(FakeHttpSession):
        def __init__(self):
            super().__init__()
            self.in_flight = 0
            self.max_in_flight = 0
            self.guard = threading.Lock()

        def get(self, url, params=None, **kwargs):
            with self.guard:
                self.in_flight += 1
                self.max_in_flight = max(self.max_in_flight, self.in_flight)
            time.sleep(0.02)
            with self.guard:
                self.in_flight -= 1
            return FakeResponse(payload=OK)

    session = SlowSession()
    client = WikiHttpClient(tmp_settings, CONTACT, session=session)
    threads = [threading.Thread(target=client.get, args=({"action": "query"},)) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert session.max_in_flight == 1


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
