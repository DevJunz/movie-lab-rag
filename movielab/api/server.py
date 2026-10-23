"""웹 화면용 API 서버 (SPEC-F2013). Streamlit과 같은 서비스를 쓰는 두 번째 UI다.

    python -m movielab.api.server            # http://127.0.0.1:8000 (A-27)

`create_app(services)`는 서비스를 주입받는다 — 테스트는 가짜 서비스를, 실행은 container의
실제 서비스를 넘긴다. `services`가 주는 것: `catalog`, `qa`, `guide`, `factcheck`, `explore`,
`profile`, `settings`, `health()`.

오류는 `{"error": {"code", "message"}}`로만 보낸다. 예외 메시지 · traceback은 로그에만 (NF2004).
"""

from __future__ import annotations

import argparse
import json
import logging
import queue
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from movielab.api import schemas
from movielab.core import messages
from movielab.core.errors import MovieLabUserError

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

# 안내 오류 코드 → (HTTP 상태, API 오류 코드). 표에 없는 코드는 500 INTERNAL (A-28)
_USER_ERRORS: dict[str, tuple[int, str]] = {
    "API_KEY_MISSING": (503, "API_KEY_MISSING"),
    "INDEX_EMPTY": (503, "INDEX_EMPTY"),
    "ITEM_NOT_INDEXED": (409, "ITEM_NOT_INDEXED"),
    "ITEM_NOT_FOUND": (400, "BAD_REQUEST"),
}

_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status: {"model": schemas.ErrorResponse} for status in (400, 409, 500, 503)
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.message = message

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


def create_app(services: Any) -> FastAPI:
    profile = services.profile
    labels = profile.labels()
    ui = services.settings.ui

    app = FastAPI(title=messages.APP_TITLE, version="1.0")

    def bad_request() -> ApiError:
        text = messages.render("BAD_REQUEST", labels, max_chars=f"{ui.max_input_chars:,}")
        return ApiError(400, "BAD_REQUEST", text)

    def to_api_error(error: Exception) -> ApiError:
        if isinstance(error, ApiError):
            return error
        if isinstance(error, MovieLabUserError):
            logger.warning("안내 오류: %s", error)
            status, code = _USER_ERRORS.get(error.code, (500, "INTERNAL"))
            if code == "BAD_REQUEST":
                return bad_request()
            return ApiError(status, code, messages.render(error.code, labels))
        logger.error("API 처리 실패", exc_info=error)
        return ApiError(500, "INTERNAL", messages.render("GENERIC_ERROR", labels))

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(error.body(), status_code=error.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(_: Request, error: RequestValidationError) -> JSONResponse:
        api_error = bad_request()
        return JSONResponse(api_error.body(), status_code=api_error.status)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, error: Exception) -> JSONResponse:
        api_error = to_api_error(error)
        return JSONResponse(api_error.body(), status_code=api_error.status)

    def require_ready() -> None:
        """키 · 메타 색인이 있어야 하는 경로 (F2012와 같은 판단)."""
        health = services.health()
        if not health.api_key_ok:
            raise ApiError(503, "API_KEY_MISSING", messages.render("API_KEY_MISSING", labels))
        if health.meta_count <= 0:
            raise ApiError(503, "INDEX_EMPTY", messages.render("INDEX_EMPTY", labels))

    def text_input(value: str) -> str:
        text = value.strip()
        if not text or len(text) > ui.max_input_chars:
            raise bad_request()
        return text

    def movie(movie_id: str) -> Any:
        item = services.catalog.get(movie_id)
        if item is None:
            raise bad_request()
        return item

    def call(action: Callable[[], Any]) -> Any:
        try:
            return action()
        except Exception as error:
            raise to_api_error(error) from None

    def notices(codes: list[str], *, no_external: bool = False) -> list[schemas.Notice]:
        all_codes = list(dict.fromkeys([*codes, *(["NO_EXTERNAL_DOCS"] if no_external else [])]))
        return [schemas.Notice(code=c, message=messages.render(c, labels)) for c in all_codes]

    def citations(cited: list[Any]) -> list[schemas.Citation]:
        return [
            schemas.Citation(
                n=e.n,
                source_type=e.source_type,
                title=messages.evidence_title(e),
                url=e.url or "",
                license=e.license,
            )
            for e in cited
        ]

    def answer_response(result: Any) -> schemas.AnswerResponse:
        return schemas.AnswerResponse(
            answer=result.answer,
            citations=citations(result.cited),
            uncited=result.uncited,
            not_found=result.not_found,
            notices=notices(result.notices, no_external=result.no_external),
            collected_titles=list(result.collect.indexed_titles),
            timings=dict(result.timings),
        )

    @app.get("/api/health", response_model=schemas.HealthResponse)
    def health() -> schemas.HealthResponse:
        status = services.health()
        return schemas.HealthResponse(
            api_key_configured=status.api_key_ok,
            index=schemas.IndexCounts(meta=status.meta_count, docs=status.docs_count),
        )

    @app.get("/api/movies", response_model=list[schemas.MovieSummary], responses=_ERROR_RESPONSES)
    def movies(q: str = "", limit: int | None = None) -> list[schemas.MovieSummary]:
        size = ui.movie_search_limit if limit is None else max(1, limit)
        needle = q.strip().casefold()
        found = []
        for item in call(services.catalog.items):
            if needle and needle not in item.title.casefold():
                continue
            found.append(
                schemas.MovieSummary(
                    movie_id=item.item_id,
                    title=item.title,
                    year=item.year,
                    genres=str(item.metadata.get("genres") or ""),
                )
            )
            if len(found) >= size:
                break
        return found

    @app.post("/api/ask", response_model=schemas.AnswerResponse, responses=_ERROR_RESPONSES)
    def ask(body: schemas.AskRequest) -> schemas.AnswerResponse:
        require_ready()
        question = text_input(body.question)
        item = movie(body.movie_id)
        return answer_response(call(lambda: services.qa.ask(item.item_id, question)))

    @app.post(
        "/api/ask/stream",
        responses={200: {"content": {"application/x-ndjson": {}}}, **_ERROR_RESPONSES},
    )
    def ask_stream(body: schemas.AskRequest) -> StreamingResponse:
        require_ready()
        question = text_input(body.question)
        item = movie(body.movie_id)
        events: queue.Queue[dict[str, Any] | None] = queue.Queue()

        def on_progress(stage: str, info: dict[str, Any]) -> None:
            text = messages.progress_text(stage, info, profile)
            if text:
                events.put(schemas.StageEvent(stage=stage, message=text).model_dump())

        def work() -> None:
            try:
                result = services.qa.ask(item.item_id, question, on_progress)
                events.put({"type": "result", "data": answer_response(result).model_dump()})
            except Exception as error:
                events.put({"type": "error", **to_api_error(error).body()})
            finally:
                events.put(None)

        def lines() -> Iterator[str]:
            threading.Thread(target=work, daemon=True).start()
            while (event := events.get()) is not None:
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.post("/api/guide", response_model=schemas.GuideResponse, responses=_ERROR_RESPONSES)
    def guide(body: schemas.GuideRequest) -> schemas.GuideResponse:
        require_ready()
        item = movie(body.movie_id)
        result = call(lambda: services.guide.generate(item.item_id))
        return schemas.GuideResponse(
            markdown=result.markdown,
            citations=citations(result.cited),
            uncited=result.uncited,
            notices=notices(list(result.collect.notices)),
        )

    @app.post(
        "/api/factcheck", response_model=schemas.FactCheckResponse, responses=_ERROR_RESPONSES
    )
    def factcheck(body: schemas.FactCheckRequest) -> schemas.FactCheckResponse:
        require_ready()
        claim = text_input(body.claim)
        item = movie(body.movie_id)
        result = call(lambda: services.factcheck.check(item.item_id, claim))
        return schemas.FactCheckResponse(
            claim=result.claim,
            verdict=result.verdict,
            reason=result.reason,
            citations=citations(result.cited),
            notices=notices(list(result.collect.notices)),
        )

    @app.post("/api/explore", response_model=schemas.ExploreResponse, responses=_ERROR_RESPONSES)
    def explore(body: schemas.ExploreRequest) -> schemas.ExploreResponse:
        require_ready()
        condition = text_input(body.condition)
        result = call(lambda: services.explore.search(condition))
        items = [
            schemas.ExploreMovie(
                movie_id=e.item.item_id,
                title=e.item.title,
                year=e.item.year,
                genres=str(e.item.metadata.get("genres") or ""),
                caption=profile.item_caption(e.item) if profile.item_caption else "",
                reason=e.reason,
            )
            for e in result.items
        ]
        message = None if items else messages.render("EXPLORE_EMPTY", labels)
        return schemas.ExploreResponse(items=items, candidates=result.candidates, message=message)

    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


def main(argv: list[str] | None = None) -> None:
    """실제 서비스로 서버를 띄운다 — 로컬 실행만 (A-27)."""
    import uvicorn

    from movielab.config import load_settings
    from movielab.container import build_services
    from movielab.core.logs import configure_from_settings

    parser = argparse.ArgumentParser(description="Movie Lab 웹 API 서버 (F2013)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    settings = load_settings()
    configure_from_settings(settings)  # traceback은 logs/movielab.log에만 (NF2004)
    uvicorn.run(create_app(build_services(settings)), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
