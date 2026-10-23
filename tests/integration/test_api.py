"""SPEC-F2013 웹 화면용 API 서버 — 가짜 서비스를 주입한 `TestClient`."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from movielab.core.errors import ItemNotIndexedError
from movielab.core.types import (
    AnswerResult,
    CollectReport,
    Evidence,
    ExploreItem,
    ExploreResult,
    FactCheckResult,
    GuideResult,
)
from movielab.data.domain_movie import MOVIE_PROFILE
from movielab.data.movies import load_items
from movielab.services.catalog import Catalog
from movielab.services.health import HealthStatus

SECRET = "sk-should-never-leak"


def _evidence(n: int) -> Evidence:
    return Evidence(
        n=n, chunk_id=f"c{n}", source_kind="wiki", source_type="위키백과", title=f"문서{n}",
        url=f"https://example.invalid/{n}", license="CC BY-SA 4.0", text="[합성] 본문",
    )  # fmt: skip


def _report(movie_id: str, question: str) -> CollectReport:
    return CollectReport(item_id=movie_id, question=question)


class FakeQA:
    def __init__(self) -> None:
        self.error: Exception | None = None

    def ask(self, movie_id, question, on_progress=None):
        if on_progress is not None:
            on_progress("extract_queries", {})
            on_progress("retrieve", {})
            on_progress("generate", {})
        if self.error is not None:
            raise self.error
        evidences = [_evidence(n) for n in (1, 2, 3)]
        return AnswerResult(
            answer=f"[합성] {movie_id} 답 [근거 1][근거 3]", evidences=evidences,
            cited=[evidences[0], evidences[2]], uncited=False, not_found=False,
            collect=_report(movie_id, question), notices=["SOURCE_FALLBACK"],
            timings={"total": 1.5},
        )  # fmt: skip


class FakeGuide:
    def generate(self, movie_id, on_progress=None):
        ev = _evidence(1)
        return GuideResult(
            markdown="## 제작 배경\n[근거 1]", evidences=[ev], cited=[ev], uncited=False,
            collect=_report(movie_id, "가이드"),
        )  # fmt: skip


class FakeFactCheck:
    def check(self, movie_id, claim, on_progress=None):
        ev = _evidence(2)
        return FactCheckResult(
            claim=claim, verdict="사실", reason="[근거 2]", evidences=[ev], cited=[ev],
            collect=_report(movie_id, claim),
        )  # fmt: skip


class FakeExplore:
    def __init__(self, catalog) -> None:
        self.catalog = catalog

    def search(self, condition, on_progress=None):
        item = self.catalog.items()[0]
        return ExploreResult(
            condition=condition, parsed={}, candidates=5, items=[ExploreItem(item, "이유")]
        )


class FakeServices:
    def __init__(self, movies_path, settings) -> None:
        self.catalog = Catalog(lambda: load_items(movies_path))
        self.qa = FakeQA()
        self.guide = FakeGuide()
        self.factcheck = FakeFactCheck()
        self.explore = FakeExplore(self.catalog)
        self.profile = MOVIE_PROFILE
        self.settings = settings
        self.status = HealthStatus(api_key_ok=True, meta_count=12, docs_count=34)

    def health(self):
        return self.status


@pytest.fixture
def services(movies_small_path, tmp_settings):
    return FakeServices(movies_small_path, tmp_settings)


@pytest.fixture
def client(services):
    from movielab.api.server import create_app

    return TestClient(create_app(services), raise_server_exceptions=False)


def _movie_id(services) -> str:
    return services.catalog.items()[0].item_id


def test_tc_f2013_01_ask(client, services):
    movie_id = _movie_id(services)
    res = client.post("/api/ask", json={"movie_id": movie_id, "question": "질문"})
    assert res.status_code == 200
    body = res.json()
    assert set(body) >= {
        "answer", "citations", "uncited", "not_found", "notices", "collected_titles", "timings",
    }  # fmt: skip
    assert [c["n"] for c in body["citations"]] == [1, 3]  # 인용된 근거만
    first = body["citations"][0]
    assert set(first) == {"n", "source_type", "title", "url", "license"}
    assert first["license"] == "CC BY-SA 4.0"
    assert body["notices"][0]["code"] == "SOURCE_FALLBACK"
    assert body["notices"][0]["message"]


def test_tc_f2013_02_stream(client, services):
    movie_id = _movie_id(services)
    res = client.post("/api/ask/stream", json={"movie_id": movie_id, "question": "질문"})
    assert res.status_code == 200
    lines = [json.loads(line) for line in res.text.splitlines() if line.strip()]
    stages = [x for x in lines if x["type"] == "stage"]
    results = [x for x in lines if x["type"] == "result"]
    assert len(stages) >= 2
    assert all(s["message"] for s in stages)
    assert len(results) == 1 and lines[-1]["type"] == "result"
    assert results[0]["data"]["citations"][0]["n"] == 1


def test_tc_f2013_03_internal_error(client, services):
    services.qa.error = RuntimeError(f"boom {SECRET}")
    res = client.post("/api/ask", json={"movie_id": _movie_id(services), "question": "질문"})
    assert res.status_code == 500
    assert res.json()["error"]["code"] == "INTERNAL"
    assert "Traceback" not in res.text and SECRET not in res.text and "boom" not in res.text


def test_tc_f2013_03_stream_error_line(client, services):
    services.qa.error = RuntimeError(f"boom {SECRET}")
    res = client.post("/api/ask/stream", json={"movie_id": _movie_id(services), "question": "질"})
    last = json.loads(res.text.strip().splitlines()[-1])
    assert last["type"] == "error" and last["error"]["code"] == "INTERNAL"
    assert SECRET not in res.text and "Traceback" not in res.text


@pytest.mark.parametrize(
    ("case", "status", "code"),
    [
        ("no_key", 503, "API_KEY_MISSING"),
        ("no_index", 503, "INDEX_EMPTY"),
        ("empty_question", 400, "BAD_REQUEST"),
        ("too_long", 400, "BAD_REQUEST"),
        ("unknown_movie", 400, "BAD_REQUEST"),
        ("not_indexed", 409, "ITEM_NOT_INDEXED"),
        ("bad_json", 400, "BAD_REQUEST"),
    ],
)
def test_tc_f2013_04_error_codes(client, services, case, status, code):
    movie_id, question = _movie_id(services), "질문"
    if case == "no_key":
        services.status = HealthStatus(api_key_ok=False, meta_count=12, docs_count=0)
    elif case == "no_index":
        services.status = HealthStatus(api_key_ok=True, meta_count=0, docs_count=0)
    elif case == "empty_question":
        question = "   "
    elif case == "too_long":
        question = "가" * (services.settings.ui.max_input_chars + 1)
    elif case == "unknown_movie":
        movie_id = "no-such-id"
    elif case == "not_indexed":
        services.qa.error = ItemNotIndexedError("x")
    payload = {"question": question} if case == "bad_json" else {"movie_id": movie_id}
    if case != "bad_json":
        payload["question"] = question
    res = client.post("/api/ask", json=payload)
    assert res.status_code == status
    error = res.json()["error"]
    assert error["code"] == code and error["message"]


def test_tc_f2013_04_health_and_movies_without_key(client, services):
    services.status = HealthStatus(api_key_ok=False, meta_count=0, docs_count=0)
    assert client.get("/api/health").json() == {
        "api_key_configured": False,
        "index": {"meta": 0, "docs": 0},
    }
    res = client.get("/api/movies", params={"q": services.catalog.items()[0].title[:1]})
    assert res.status_code == 200
    first = res.json()[0]
    assert set(first) == {"movie_id", "title", "year", "genres"}


def test_tc_f2013_04_other_endpoints(client, services):
    movie_id = _movie_id(services)
    guide = client.post("/api/guide", json={"movie_id": movie_id}).json()
    assert guide["markdown"].startswith("## 제작 배경") and guide["citations"][0]["n"] == 1
    fact = client.post("/api/factcheck", json={"movie_id": movie_id, "claim": "주장"}).json()
    assert fact["verdict"] == "사실" and fact["citations"][0]["n"] == 2
    explore = client.post("/api/explore", json={"condition": "조건"}).json()
    assert explore["items"][0]["movie_id"] == movie_id
    assert set(explore["items"][0]) == {"movie_id", "title", "year", "genres", "director", "reason"}


def test_tc_f2013_05_static(client):
    index = client.get("/")
    assert index.status_code == 200 and "text/html" in index.headers["content-type"]
    for element_id in ('id="question-input"', 'id="answer-area"', 'id="evidence-area"'):
        assert element_id in index.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert "cdn" not in index.text.lower()


def test_tc_f2013_06_openapi(client):
    spec = client.get("/openapi.json").json()
    paths = set(spec["paths"])
    assert paths >= {
        "/api/health", "/api/movies", "/api/ask", "/api/ask/stream",
        "/api/guide", "/api/factcheck", "/api/explore",
    }  # fmt: skip
    schemas = set(spec["components"]["schemas"])
    assert schemas >= {
        "AnswerResponse", "GuideResponse", "FactCheckResponse", "ExploreResponse",
        "ErrorResponse", "Citation", "HealthResponse", "MovieSummary",
    }  # fmt: skip
