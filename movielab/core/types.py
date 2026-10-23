"""도메인 중립 자료형 (01-architecture.md §4.4). 도메인 고유 필드 이름은 metadata 안에만 둔다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 청크 메타데이터의 항목 ID 키 — 검색 필터 · 청크 ID · 고아 판별에 쓴다
ITEM_KEY = "movie_id"


@dataclass(frozen=True)
class ItemRecord:
    """항목 1건 = 색인 텍스트 1개 (F2001)."""

    item_id: str
    title: str
    year: int
    index_text: str
    metadata: dict[str, Any]
    url: str

    @property
    def display_name(self) -> str:
        return f"{self.title} ({self.year})"


@dataclass(frozen=True)
class LoadResult:
    items: list[ItemRecord] = field(default_factory=list)
    skipped: int = 0


@dataclass(frozen=True)
class ReindexReport:
    """외부 문서 재색인 결과 (F2005 §3.3). `total_chunks`는 재색인 후 컬렉션 전체 청크 수."""

    documents: int
    chunks: int
    failed: int = 0
    removed: int = 0  # 저장 원문이 없어 청크를 지운 문서 수
    total_chunks: int = 0


@dataclass(frozen=True)
class IndexReport:
    """메타 색인 결과 (F2002).

    `loaded`는 로드한 원소 수(항목 + 건너뜀), `indexed`는 로드한 ID 중 색인된 수.
    """

    loaded: int
    skipped: int
    indexed: int
    failed_batches: list[int] = field(default_factory=list)
    removed: int = 0  # 데이터에서 빠져 지운 고아 문서 수

    @property
    def ok(self) -> bool:
        return self.loaded - self.skipped == self.indexed and not self.failed_batches


@dataclass(frozen=True)
class PdfIndexReport:
    """PDF 1건 색인 결과 (F2016). `missing`이면 파일이 없어 건너뛰었다."""

    file: str
    pages: int = 0
    chunks: int = 0
    skipped_pages: list[int] = field(default_factory=list)
    missing: bool = False


# --- 외부 문서 수집 (SPEC-F2004) ---


@dataclass(frozen=True)
class Candidate:
    """검색 · 제목 조회로 찾은 문서 후보. 본문은 아직 없다 (제목 · 요약만)."""

    page_id: str
    title: str
    snippet: str = ""
    size: int = 0
    query: str = ""
    url: str = ""
    matched_title: str = ""  # 제목 조회 때 요청한 제목 (넘겨주기 전)
    disambiguation: bool = False


@dataclass(frozen=True)
class SourceDocument:
    """수집한 문서 1건 (01-architecture §4.2 형식)."""

    page_id: str
    title: str
    url: str
    text: str
    source: str
    movie_id: str
    related_movie: str
    search_query: str
    collected_at: str
    source_kind: str = "wiki"
    license: str = "CC BY-SA 4.0"
    is_item_doc: bool = False


@dataclass(frozen=True)
class Rejection:
    page_id: str
    title: str
    # p2_not_selected · over_limit · too_short · disambiguation · already_collected · fetch_failed
    reason: str


@dataclass
class CollectReport:
    """수집 결과 — 진행 상태 · 수집 상세 화면과 스크립트 출력의 원본 (V4.2-1, V4.2-2)."""

    item_id: str
    question: str
    queries: list[str] = field(default_factory=list)
    cached_queries: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    selected: list[Candidate] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    item_doc_title: str | None = None
    indexed_titles: list[str] = field(default_factory=list)
    indexed_chunks: int = 0
    saved_paths: list[Any] = field(default_factory=list)
    source_used: str = ""
    notices: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


# --- 근거 (SPEC-F2006 ~ F2008) ---


@dataclass(frozen=True)
class Evidence:
    """답변 생성에 넣는 근거 1개. `n`은 `[근거 n]` 번호다."""

    n: int
    chunk_id: str
    source_kind: str  # meta · wiki · pdf
    source_type: str  # 화면 · 프롬프트에 보일 출처 유형 라벨
    title: str
    url: str
    license: str | None
    text: str
    score: float | None = None  # 외부 근거: 코사인 유사도 (클수록 가깝다)
    page: int | None = None  # PDF 쪽 번호 (F2016)
    file: str | None = None  # PDF 파일명 (F2016)


@dataclass(frozen=True)
class CitedResult:
    """답변에 실제로 인용된 근거 (F2008). `cited`는 번호 오름차순, 번호는 원래 번호 그대로."""

    cited: list[Evidence]
    uncited: bool


@dataclass(frozen=True)
class ExploreItem:
    """조건 탐색 결과 하나 — 항목과 선정 이유 (F2011)."""

    item: ItemRecord
    reason: str


@dataclass(frozen=True)
class ExploreResult:
    condition: str
    parsed: dict[str, Any]
    candidates: int  # 의미 검색 후보 수
    items: list[ExploreItem] = field(default_factory=list)


@dataclass(frozen=True)
class AnswerResult:
    """질문 하나의 결과 (F2009 `QAService.ask`).

    `evidences`는 검색된 근거 전체, `cited`는 인용된 것만.
    """

    answer: str
    evidences: list[Evidence]
    cited: list[Evidence]
    uncited: bool
    not_found: bool
    collect: CollectReport
    no_external: bool = False  # 외부 근거가 하나도 없음 (F2012 안내)
    notices: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    evidences: list[Evidence]
    no_external: bool = False
