"""웹 API 요청 · 응답 형식 (SPEC-F2013 §3). `/docs`(OpenAPI)에 그대로 나온다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    movie_id: str
    question: str


class GuideRequest(BaseModel):
    movie_id: str


class FactCheckRequest(BaseModel):
    movie_id: str
    claim: str


class ExploreRequest(BaseModel):
    condition: str


class IndexCounts(BaseModel):
    meta: int
    docs: int


class HealthResponse(BaseModel):
    api_key_configured: bool
    index: IndexCounts


class MovieSummary(BaseModel):
    movie_id: str
    title: str
    year: int
    genres: str


class Citation(BaseModel):
    n: int
    source_type: str
    title: str
    url: str
    license: str | None = None


class Notice(BaseModel):
    code: str
    message: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation]
    uncited: bool
    not_found: bool
    notices: list[Notice] = Field(default_factory=list)
    collected_titles: list[str] = Field(default_factory=list)
    timings: dict[str, float] = Field(default_factory=dict)


class GuideResponse(BaseModel):
    markdown: str
    citations: list[Citation]
    uncited: bool
    notices: list[Notice] = Field(default_factory=list)


class FactCheckResponse(BaseModel):
    claim: str
    verdict: str
    reason: str
    citations: list[Citation]
    notices: list[Notice] = Field(default_factory=list)


class ExploreMovie(BaseModel):
    movie_id: str
    title: str
    year: int
    genres: str
    caption: str  # 도메인 프로필의 한 줄 요약 (장르 · 감독 …)
    reason: str


class ExploreResponse(BaseModel):
    items: list[ExploreMovie]
    candidates: int
    message: str | None = None


ErrorCode = Literal["API_KEY_MISSING", "INDEX_EMPTY", "ITEM_NOT_INDEXED", "BAD_REQUEST", "INTERNAL"]


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class StageEvent(BaseModel):
    """NDJSON 스트림의 진행 단계 줄. 마지막 줄은 `{"type":"result","data":AnswerResponse}`."""

    type: Literal["stage"] = "stage"
    stage: str
    message: str
