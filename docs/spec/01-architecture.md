# 01. 아키텍처 · 데이터 · 테스트 설계

| 항목 | 내용 |
|---|---|
| 문서 종류 | SPEC 공통 문서 (모든 SPEC이 참조) |
| 관련 요구사항 | NF2005(모듈 분리) 중심, 전 요구사항 공통 |
| 상태 | Draft |

이 문서는 SPEC들이 공유하는 **구조 · 데이터 모델 · 설정 · 프롬프트 계약 · 테스트 전략**을 정한다.
개별 SPEC은 여기의 이름과 규칙을 그대로 쓴다. 여기를 바꾸면 영향받는 SPEC도 같은 PR에서 고친다.

---

## 1. 기술 스택과 고정 버전 (명세서 1.2)

`requirements.txt`는 아래 버전을 **그대로** 고정한다(`==`). 버전을 바꾸지 않는다.

```text
langchain==1.3.14
langgraph==1.2.10
langsmith==0.10.17
langchain-core==1.6.0
langchain-openai==1.4.3
langchain-community==0.4.2
langchain-chroma==1.1.0
langchain-text-splitters==1.1.2
chromadb==1.5.9
openai==2.54.0
streamlit==1.62.0
requests==2.34.2
python-dotenv==1.2.3
typing-extensions==4.16.0
```

심화(F2013)용 `requirements-advanced.txt`:

```text
fastapi==0.141.1
uvicorn[standard]==0.52.4
pydantic==2.13.5
pypdf            # F2016. 명세서에 버전 지정 없음 → SPEC-F2016 구현 PR에서 고정
```

개발용 `requirements-dev.txt`: `pytest`, `ruff` (버전은 SPEC-NF2005 PR에서 고정, 가정 A-13).

- Python **3.10+**. 3.11 이상 전용 기능(`tomllib`, `typing.Self`, `ExceptionGroup`, `except*`)은 쓰지 않는다.
- LLM · 임베딩은 **SSAFY GMS(OpenAI 호환)** 를 `langchain-openai`의 `ChatOpenAI` · `OpenAIEmbeddings`에 `base_url`과 `api_key`를 넘겨 호출한다.

## 2. 모듈 구조 (NF2005)

명세서 1.2의 다섯 영역(데이터 준비 · Vector Store · RAG 파이프라인 · 서비스 기능 · UI)을 패키지로 나누고,
**도메인(영화)에 묶인 코드는 `movielab/data/`에만 둔다.**

```text
ai_project_02/                       # 저장소 루트 (GitHub: movie-lab-rag)
├─ AGENTS.md  CLAUDE.md  README.md  .gitignore  .env.example
├─ requirements.txt  requirements-dev.txt  requirements-advanced.txt  pyproject.toml
├─ config/settings.json              # 조정 가능한 설정 (비밀 값 없음)
├─ .streamlit/config.toml            # showErrorDetails 끔 (NF2004)
├─ .github/workflows/ci.yml          # CI (NF2005에서 도입)
├─ movielab/
│  ├─ config.py                      # 설정 로드: settings.json + .env (NF2003)
│  ├─ container.py                   # 조립 지점(composition root). 구체 구현을 연결한다
│  ├─ providers.py                   # GMS 채팅 · 임베딩 모델 생성
│  ├─ prompts.py                     # 프롬프트 템플릿 (도메인 문구는 DomainProfile에서 주입)
│  ├─ core/                          # 도메인 중립 자료형 · 공통 유틸
│  │  ├─ types.py                    # ItemRecord, SourceDocument, Candidate, Evidence, AnswerResult …
│  │  ├─ domain.py                   # DomainProfile 자료형(필드 정의만)
│  │  ├─ jsonparse.py                # LLM 출력의 JSON 배열 · 객체 파싱(폴백 포함)
│  │  ├─ messages.py                 # 사용자 안내 문구 (F2012)
│  │  └─ errors.py                   # 사용자 안내용 예외
│  ├─ data/                          # ◀ 데이터 준비 영역 — 영화 도메인 종속 코드는 여기에만
│  │  ├─ domain_movie.py             # 영화 DomainProfile 값, 항목 자체 문서 판별 규칙
│  │  ├─ movies.py                   # movies.json 로드 → ItemRecord (F2001)
│  │  ├─ wiki_api.py                 # 한국어 위키백과 API 소스 (F2004, NF2006)
│  │  ├─ wiki_bundle.py              # 제공 문서 묶음 소스 (대비책)
│  │  ├─ raw_store.py                # 수집 원문 JSON 저장 (data/raw/wiki/)
│  │  └─ pdf_source.py               # PDF 소스 (F2016)
│  ├─ collect/                       # 수집 (F2003, F2004, NF2002)
│  │  ├─ query_extractor.py          # 프롬프트 1
│  │  ├─ selector.py                 # 프롬프트 2 + 제외 · 우선 규칙
│  │  ├─ manifest.py                 # 수집 매니페스트 (캐시)
│  │  └─ collector.py                # 수집 오케스트레이션 + 진행 상태 콜백
│  ├─ index/                         # 색인 (F2002, F2005)
│  │  ├─ store.py                    # Chroma 클라이언트 · 컬렉션 생성 · 조회 · 건수
│  │  ├─ meta_indexer.py             # RAG 1
│  │  └─ doc_indexer.py              # RAG 2 (청킹)
│  ├─ rag/                           # 검색 · 생성 (F2006~F2008)
│  │  ├─ retriever.py                # 메타 고정 포함 + 외부 청크 검색 + 병합 · 중복 제거
│  │  ├─ graph.py                    # LangGraph: retrieve → generate
│  │  └─ citations.py                # [근거 n] 추출 · 인용 근거 선별
│  ├─ services/                      # 서비스 기능 (F2009~F2012 오케스트레이션)
│  │  ├─ qa.py                       # 질문 → 수집 → 그래프 → AnswerResult
│  │  ├─ guide.py                    # 관람 가이드 (F2010)
│  │  ├─ factcheck.py                # 사실 여부 판정 (F2010)
│  │  ├─ explore.py                  # 조건 기반 탐색 (F2011)
│  │  └─ health.py                   # 키 · 색인 상태 점검 (F2012)
│  ├─ ui/streamlit_app.py            # Streamlit 화면 (F2009, F2012)
│  └─ api/                           # FastAPI 서버 (F2013): server.py, schemas.py
├─ web/                              # HTML · CSS · JS 화면 (F2013)
├─ scripts/                          # 실행 스크립트 (python -m scripts.<이름>)
│  ├─ index_meta.py                  # RAG 1 색인
│  ├─ collect.py                     # 영화 1편 · 질문 1개 수집 + 색인
│  ├─ prewarm.py                     # 대표 질문 사전 수집
│  ├─ reindex_docs.py                # 저장된 원문으로 RAG 2 재색인 (청크 설정 비교)
│  ├─ show_graph.py                  # LangGraph 구조 mermaid 출력 (F2007)
│  ├─ measure_latency.py             # 대표 질문 처리 시간 측정 (NF2001)
│  ├─ compare_retrieval.py           # 유사도 vs MMR (F2014)
│  ├─ compare_rag.py                 # RAG 전후 비교 (F2015)
│  └─ index_pdf.py                   # PDF 색인 (F2016)
├─ tests/
│  ├─ conftest.py                    # 네트워크 차단, 공통 픽스처
│  ├─ fakes/                         # FakeChatModel, FakeEmbeddings, FakeHttpSession, FakeClock
│  ├─ fixtures/                      # 합성 데이터 (movies_small.json, wiki_small/ …)
│  ├─ unit/  integration/  live/
├─ docs/
│  ├─ spec/                          # SPEC (이 폴더)
│  ├─ verification/                  # questions.json, 실행 결과, 스크린샷
│  └─ deliverables/                  # 제출 문서 (03-deliverables.md 참고)
├─ data/                             # (gitignore) chroma/, raw/, manifest.json, pdf/
└─ 영화도메인_데이터_배포용/         # (gitignore) 제공 데이터 팩
```

### 2.1 의존 규칙

화살표 방향으로만 import 한다. **같은 영역 안의 import는 항상 허용한다.** `tests/unit/test_architecture.py`가 AST로 검사한다(SPEC-NF2005).

| 패키지 | import 허용 대상 |
|---|---|
| `core` | 표준 라이브러리, `langchain_core` 자료형 |
| `config`, `providers`, `prompts` | `core` |
| `data` | `core`, `config` |
| `collect`, `index`, `rag` | `core`, `config`, `prompts` (**`data` 금지** — 구현은 주입받는다) |
| `services` | `core`, `config`, `prompts`, `collect`, `index`, `rag` |
| `container` | 전부 (구체 구현을 조립하는 유일한 곳) |
| `ui`, `api` | `core`, `config`, `services`, `container` (**`data` · `index` · `rag` 직접 import 금지**) |
| `scripts` | `container`, `services`, `core`, `config` |

도메인 문구("영화 큐레이터", "영화 메타데이터" 등)는 `data/domain_movie.py`의 `DomainProfile` 값으로만 존재하고,
`prompts.py` · `core/messages.py`는 그 값을 받아 문장을 만든다. 다른 도메인으로 바꿀 때는 `data/`만 교체한다.

## 3. 처리 흐름

### 3.1 사전 색인 (RAG 1)

```text
movies.json ─(data.movies.load_items)→ ItemRecord×964 ─(index.meta_indexer)→ Chroma "movie_meta" (id = movie_id)
```

### 3.2 질문 처리 (S1 · S2)

```text
UI ─ services.qa.ask(movie_id, question, on_progress)
     │
     ├─ ① collect.collector.collect(item, question)                ← LangGraph 밖 (진행 상태 표시 대상)
     │     ├─ 매니페스트 확인: 이 질문 · 검색어 · 문서를 이미 수집했나? (NF2002)
     │     ├─ 프롬프트 1: 검색어 추출 (+ 항목 자체 문서 검색어 강제 추가)   F2003
     │     ├─ 소스 검색: 위키 API 또는 제공 묶음 → 후보(제목 · 요약)      F2004, NF2006
     │     ├─ 프롬프트 2: 후보 선별 + 제외 규칙 + 항목 자체 문서 강제 포함  F2004
     │     ├─ 본문 · 원문 URL 수집 → data/raw/wiki/ 저장
     │     └─ index.doc_indexer: 청킹 → Chroma "wiki_docs"                F2005
     │
     ├─ ② rag.graph.invoke({movie_id, question, task:"qa"})          ← LangGraph 노드 2개
     │     ├─ retrieve: 메타 청크(항상) + 위키 청크 Top-k → 병합 · 중복 제거 · 번호 부여   F2006
     │     └─ generate: 프롬프트 3 → 답변 ([근거 n])                                       F2007
     │
     └─ ③ rag.citations: 인용된 근거만 추림, 인용 0건 안내                  F2008
           → AnswerResult
```

수집을 그래프 밖에 두는 이유: 명세서 F2007은 그래프를 **retrieve와 generate 두 노드**로 구성하라고 정한다.
수집은 질문마다 일어나지 않을 수 있고(캐시 적중), 진행 상태를 UI에 단계별로 보여야 하므로 서비스 계층이 그래프 호출 전에 수행한다.

## 4. 데이터 모델

### 4.1 항목 메타데이터 (`movies.json`)

배열 하나, 원소 하나가 영화 1편이다(964편). 실제 파일을 확인한 결과는 아래와 같다.

| 필드 | 타입 | 비고 (실데이터 확인) |
|---|---|---|
| `movie_id` | str | TMDB ID. **문자열**. 위키 파일명 접두어와 같다 |
| `title`, `original_title` | str | **같은 제목의 영화가 있다** (예: 「미녀와 야수」 1991 · 2017, 「괴물」 1982 · 2006, 「라이온 킹」, 「알라딘」 …) → 화면 · 프롬프트에는 항상 `제목 (연도)`로 표기 |
| `release_date`, `year` | str, int | 연도 범위 1938~2026, 누락 없음 |
| `genres` | list[str] | 비어 있는 영화 없음 |
| `director` | list[str] | **빈 목록 1건** (`1084390` 소주전쟁) → "정보 없음"으로 표기 |
| `cast` | list[str] | 최대 5명 |
| `overview` | str | 줄거리. 누락 없음 |
| `runtime` | int | 분 |
| `original_language` | str | `ko`이면 한국 영화 (168편) |
| `production_countries` | list[str] | 영문 국가명 |
| `vote_average`, `vote_count` | float, int | TMDB 평점 |
| `tmdb_url` | str | 메타 근거의 원문 출처 |

### 4.2 위키 문서 (제공 묶음 · API 수집 결과 공통 형식)

파일 위치 `movielab_wiki/wikipedia/{movie_id}_{문서제목}.json` (제목의 공백 · 괄호 · 특수문자는 `_`로 바뀜).
API로 수집한 문서도 `data/raw/wiki/`에 **같은 필드**로 저장한다.

| 필드 | 타입 | 비고 |
|---|---|---|
| `page_id` | **int** (묶음 파일) | 매니페스트의 `page_ids`는 **문자열** → 코드 내부에서는 항상 `str`로 정규화 |
| `title` | str | 문서 제목. 파일명이 아니라 이 값을 쓴다 |
| `url` | str | 원문 URL — 근거 표시용 |
| `text` | str | 평문 본문. 묶음 기준 최소 301자 · 중앙값 2,854자 · 최대 90,305자 |
| `source` | str | `한국어 위키백과` |
| `movie_id` | str | 이 문서를 모으게 한 영화 |
| `related_movie` | str | 그 영화 제목 |
| `search_query` | str | 이 문서를 찾은 검색어 |
| `collected_at` | str | `YYYY-MM-DD` |

- 같은 문서를 여러 영화가 공유한다(파일 3,725개 / 고유 문서 2,661건). 청크 ID에 반드시 `movie_id`를 넣는다(§5.2).
- 영화당 문서 수 1~10건(평균 3.86건). 1건뿐인 영화가 28편 있다 → 외부 근거가 적은 경우를 정상 흐름으로 다룬다.
- 「미녀와 야수」(동화)와 「미녀와 야수 (2017년 영화)」처럼 **제목이 같아도 영화 문서가 아닐 수 있다** → 항목 자체 문서 판별 규칙(SPEC-F2004 §3.4).

### 4.3 수집 매니페스트 (`data/manifest.json`)

제공 `wiki_manifest.json`과 호환되는 형식에 질문 캐시를 더한다(NF2002).

```json
{
  "157336": {
    "keywords": ["인터스텔라 (영화)", "웜홀", "블랙홀"],
    "titles": ["인터스텔라", "웜홀", "블랙홀"],
    "page_ids": ["475498", "20671", "151821"],
    "questions": {"인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?": ["웜홀", "블랙홀", "일반 상대성 이론"]},
    "rejected_page_ids": ["99999"],
    "chunks": 278,
    "collected_at": "2026-10-23"
  }
}
```

키 비교는 정규화(앞뒤 공백 제거, 연속 공백 1칸, 소문자화) 후에 한다.

### 4.4 내부 자료형 (`movielab/core/types.py`)

| 자료형 | 주요 필드 | 쓰는 곳 |
|---|---|---|
| `ItemRecord` | `item_id`, `title`, `year`, `index_text`, `metadata: dict`, `url` | F2001 → F2002 |
| `Candidate` | `page_id: str`, `title`, `snippet`, `size`, `query`, `is_item_doc: bool` | F2004 |
| `SourceDocument` | 4.2 필드 전부 + `source_kind`(`wiki`/`pdf`), `license` | F2004 → F2005 |
| `CollectReport` | `queries`, `cached_queries`, `candidates`, `selected`, `rejected`(사유 포함), `indexed_titles`, `source_used`(`api`/`bundle`), `notices` | F2004, F2012, V4.2 |
| `Evidence` | `n`(근거 번호), `chunk_id`, `source_kind`(`meta`/`wiki`/`pdf`), `source_type`(표시용 라벨), `title`, `url`, `license`, `text`, `score`, `page`(PDF) | F2006~F2008 |
| `AnswerResult` | `answer`, `evidences`, `cited`, `uncited: bool`, `not_found: bool`, `collect: CollectReport`, `notices`, `timings` | F2007~F2009, F2012 |

## 5. Vector DB 설계 (Chroma)

- 클라이언트: `chromadb.PersistentClient(path=settings.paths.chroma_dir)`, 텔레메트리 끔(`anonymized_telemetry=False`).
- 거리: 코사인(가정 A-19). 색인과 검색에 **같은 임베딩 모델**을 쓴다. 모델을 바꾸면 전체 재색인한다.

### 5.1 컬렉션

| 컬렉션 | 내용 | 청크 단위 | 요구사항 |
|---|---|---|---|
| `movie_meta` | 영화 메타데이터 | 영화 1편 = 청크 1개 | F2002 |
| `wiki_docs` | 위키백과 문서 청크 | 1,000자 / 중복 200자 (설정) | F2005 |
| `pdf_docs` | PDF 청크 (심화) | 쪽 안에서 800자 / 중복 100자 (설정) | F2016 |

### 5.2 청크 ID 규칙

| 컬렉션 | ID 형식 | 예 | 이유 |
|---|---|---|---|
| `movie_meta` | `{movie_id}` | `157336` | 재색인해도 덮어쓰기만 일어난다 (F2002) |
| `wiki_docs` | `{movie_id}:{page_id}:{순번}` | `157336:20671:0` | 여러 영화가 같은 문서를 공유해도 덮어쓰지 않는다 (F2005) |
| `pdf_docs` | `{movie_id}:pdf:{doc_id}:{쪽}:{순번}` | `282631:pdf:kofic2014:12:0` | 쪽 번호를 근거에 표시 (F2016) |

같은 `(movie_id, page_id)` 문서를 다시 색인할 때는 **기존 청크를 먼저 지우고** 넣는다.
청크 크기를 키워 청크 수가 줄면 남는 옛 청크(높은 순번)가 섞이기 때문이다.

### 5.3 메타데이터 필드

Chroma 메타데이터 값은 `str` · `int` · `float` · `bool`만 쓴다. 목록은 `", "`로 이어 문자열로 저장한다.

**`movie_meta`**

| 필드 | 예 | 용도 |
|---|---|---|
| `movie_id` | `"157336"` | 식별 · 필터 |
| `title`, `original_title` | `"인터스텔라"` | 근거 표시 |
| `year` | `2014` (int) | 조건 탐색 필터 (F2011) |
| `genres`, `director`, `cast` | `"모험, 드라마, SF"` | 표시 · 조건 검증 |
| `original_language` | `"en"` | 한국 영화 필터 (F2011) |
| `runtime`, `vote_average` | `169`, `8.485` | 표시 |
| `url` | `tmdb_url` | 근거 원문 출처 |
| `source_kind` / `source_type` | `"meta"` / `"영화 메타데이터"` | 출처 유형 구분 (F2007) |

**`wiki_docs`**

| 필드 | 예 | 용도 |
|---|---|---|
| `movie_id` | `"157336"` | **검색 범위 필터** — 빠지면 다른 영화 문서가 근거에 섞인다 |
| `page_id` | `"20671"` (str) | 문서 식별 |
| `title`, `url` | `"블랙홀"`, `https://ko.wikipedia.org/wiki/...` | 근거 표시 |
| `related_movie`, `search_query`, `collected_at` | | 수집 이력 추적 |
| `is_item_doc` | `true` | 항목 자체 문서 표시 (V4.2-4) |
| `chunk_index`, `chunk_size`, `chunk_overlap` | `0`, `1000`, `200` | 설정 비교 (V4.2-5) |
| `source_kind` / `source_type` / `license` | `"wiki"` / `"위키백과"` / `"CC BY-SA 4.0"` | 출처 유형 · 이용 조건 표시 |

## 6. 설정

### 6.1 비밀 값 — `.env` (NF2003)

`.env`는 Git에 올리지 않는다. 저장소에는 값이 빈 `.env.example`만 둔다.

| 변수 | 필수 | 설명 |
|---|---|---|
| `GMS_API_KEY` | 예 | SSAFY GMS 키 |
| `GMS_BASE_URL` | 예 | GMS OpenAI 호환 주소 (GMS 안내 페이지 값) |
| `WIKI_CONTACT` | API 수집 시 | 위키백과 User-Agent에 넣을 연락처 (이메일 또는 저장소 URL) |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` | 아니오 | 선택. 기본 꺼짐. CI에서는 항상 꺼짐 |

### 6.2 조정 값 — `config/settings.json`

코드가 아니라 이 파일로 바꾼다(F2005, F2006). 환경변수 `MOVIELAB_SETTINGS`로 다른 파일을 지정할 수 있다(실험 · 테스트용).

```json
{
  "paths": {
    "movies": "영화도메인_데이터_배포용/movies.json",
    "wiki_bundle": "영화도메인_데이터_배포용/movielab_wiki/wikipedia",
    "chroma_dir": "data/chroma",
    "raw_dir": "data/raw",
    "manifest": "data/manifest.json",
    "pdf_dir": "data/pdf",
    "log_file": "logs/movielab.log"
  },
  "models": {"chat": "gpt-4o-mini", "embedding": "text-embedding-3-small", "temperature": 0, "timeout_sec": 60},
  "collections": {"meta": "movie_meta", "docs": "wiki_docs", "pdf": "pdf_docs"},
  "chunking": {"chunk_size": 1000, "chunk_overlap": 200, "pdf_chunk_size": 800, "pdf_chunk_overlap": 100},
  "retrieval": {"top_k": 4, "search_type": "similarity", "mmr_fetch_k": 20, "mmr_lambda": 0.5, "pdf_top_k": 2},
  "indexing": {"batch_size": 100, "retries": 1, "retry_wait_sec": 2.0},
  "collect": {"source": "auto", "min_queries": 3, "max_queries": 5, "search_limit": 5, "max_selected_docs": 5, "min_doc_chars": 200},
  "wiki": {"api_url": "https://ko.wikipedia.org/w/api.php", "min_interval_sec": 1.0, "max_retries": 3,
           "backoff_base_sec": 1.0, "timeout_sec": 10, "maxlag": 5, "app_name": "MovieLab", "app_version": "0.1"},
  "explore": {"candidates": 20, "max_results": 10},
  "domain": {"disclaimer_enabled": false}
}
```

- 설정 로드는 `movielab.config.load_settings(path=None, env=None)` 하나로 한다. 값 검증 실패(예: `chunk_overlap >= chunk_size`, `top_k < 1`, `search_type` 오타)는 시작할 때 `SettingsError`로 알린다.
- 모델 이름은 설정 파일 값이 기본이고, 환경변수 `MOVIELAB_CHAT_MODEL` · `MOVIELAB_EMBED_MODEL`로 덮어쓸 수 있다.

## 7. 프롬프트 계약

템플릿은 `movielab/prompts.py`에 모은다. 모든 프롬프트는 첫 줄에 `[작업: …]` 머리표를 둔다
(사람이 로그를 읽기 쉽게 하고, 테스트용 가짜 LLM이 작업 종류를 알아보게 한다). 도메인 문구는 `DomainProfile`에서 주입한다.

| ID | 이름 | 역할 | 입력 | 출력 형식 | 실패 시 | SPEC |
|---|---|---|---|---|---|---|
| P1 | 검색어 추출 | `{expert_role}`(영화 큐레이터) | 영화 카드(제목 · 연도 · 원제 · 감독 · 장르 · 줄거리 앞부분), 질문 | JSON 문자열 배열 3~5개 | 빈 배열 → 항목 자체 검색어만 사용 | F2003 |
| P2 | 후보 선별 | 자료 조사원 | 영화, 질문, 번호 붙은 후보(제목 · 요약) | JSON 정수 배열(후보 번호) | 빈 배열 → 항목 자체 문서만 수집 | F2004 |
| P3 | 답변 생성 | `{assistant_role}`(영화 지식 도우미) | `[근거 n] (출처 유형) 제목` + 본문 목록, 질문 | 평문 답변. 주요 주장 끝에 `[근거 n]`. 근거 없으면 `NOT_FOUND` 문장 | — | F2007 |
| G1 | 관람 가이드 | 영화 지식 도우미 | 근거 목록, 영화 | 정해진 소제목의 마크다운, 문장마다 `[근거 n]` | — | F2010 |
| C1 | 사실 판정 | 사실 확인 담당 | 근거 목록, 주장 | JSON 객체 `{verdict, reason, citations}` | 파싱 실패 → `확인 불가` | F2010 |
| E1 | 조건 해석 | 영화 큐레이터 | 자연어 조건 | JSON 객체 `{semantic_query, year_min, year_max, korean_only}` | 기본값(조건 원문 · 필터 없음) | F2011 |
| E2 | 조건 선별 | 영화 큐레이터 | 조건, 번호 붙은 후보 메타 텍스트 | JSON 배열 `[{movie_id, reason}]` | 빈 배열 → "맞는 영화 없음" | F2011 |
| B1 | 직접 답변 (비교용) | 영화 지식 도우미 | 영화 제목 (연도), 질문. **근거 없음** | 평문 | — | F2015 (심화) |

- `NOT_FOUND` 문장은 `"제공된 문서에서 확인되지 않습니다."`로 고정하고 `core/messages.py`에 상수로 둔다.
- JSON 파싱은 `core/jsonparse.py`가 맡는다: 코드 펜스 제거 → 첫 `[`(또는 `{`)부터 마지막 `]`(또는 `}`)까지 잘라 읽기 → 실패하면 호출자가 정한 기본값.
- 화면에는 프롬프트 전문을 표시하지 않는다(NF2004). 프롬프트는 `DEBUG` 로그에만 남긴다.

## 8. LangGraph (F2007)

```python
class RAGState(TypedDict, total=False):
    movie_id: str
    question: str          # task가 factcheck이면 주장, guide이면 고정 질문
    task: str              # "qa" | "guide" | "factcheck"
    contexts: list         # list[Evidence] — retrieve가 채움
    answer: str            # generate가 채움 (factcheck은 JSON 문자열)
```

- 노드는 정확히 `retrieve`, `generate` 두 개. 간선 `START → retrieve → generate → END`.
- `generate`는 `task`에 따라 P3 · G1 · C1 중 하나를 고른다. 특화 기능(F2010)도 같은 두 노드 그래프를 쓴다.
- 그래프는 `rag.graph.build_graph(retriever, llm, profile)`로 만들고, 테스트에서는 가짜 LLM과 임시 Chroma를 주입한다.

## 9. 오류 처리와 로그 (F2012, NF2004)

- 사용자 안내가 필요한 상황은 `core/errors.py`의 예외로 표현한다: `MissingApiKeyError`, `IndexEmptyError`, `ExternalSourceUnavailableError`, `SettingsError`.
- UI · API는 예외를 잡아 `core/messages.py`의 **사용자용 문구만** 보여준다. traceback · 키 · 프롬프트는 `logs/movielab.log`에만 남긴다.
- 로그에는 단계별 소요 시간(`timings`)을 `INFO`로 남긴다(NF2001).

## 10. 테스트 전략

### 10.1 원칙

1. **CI는 결정적이다.** 실제 LLM · 임베딩 · 위키백과를 부르지 않는다. 같은 커밋은 언제 돌려도 같은 결과다.
2. 외부 의존은 모두 **생성자 주입**으로 바꿀 수 있게 만든다(LLM, 임베딩, HTTP 세션, `sleep`, 시계, 설정 경로).
3. 테스트 픽스처는 **합성 데이터**다. 위키백과 원문을 픽스처로 복사하지 않는다(CC BY-SA 고지 의무를 피하고 저장소를 가볍게 유지).
4. SPEC의 인수 조건(AC) 하나에 자동 테스트를 하나 이상 둔다. 자동화할 수 없는 항목(스크린샷 증빙)은 **수동(M)** 으로 표시하고 증빙 경로를 정한다.

### 10.2 테스트 수준과 마커

| 수준 | 위치 | 마커 | 외부 호출 | CI |
|---|---|---|---|---|
| 단위 | `tests/unit/` | (없음) | 없음 | 실행 |
| 통합 | `tests/integration/` | (없음) | 없음. 임시 폴더의 실제 Chroma + 가짜 LLM · 임베딩 · HTTP | 실행 |
| 실제 API | `tests/live/` | `@pytest.mark.live` | GMS · 위키백과 실제 호출 | **실행 안 함** |
| 수동 | `docs/verification/` | — | 사람이 실행 · 캡처 | — |

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-m 'not live' --strict-markers"
markers = ["live: 실제 GMS · 위키백과를 호출한다. CI에서 실행하지 않는다"]
```

live 테스트 실행: `pytest -m live` (로컬, `.env` 필요).

### 10.3 가짜 객체 (`tests/fakes/`)

| 가짜 | 대체 대상 | 동작 |
|---|---|---|
| `FakeChatModel` | `ChatOpenAI` | `BaseChatModel` 상속. 프롬프트 첫 줄 `[작업: …]`로 작업을 알아보고, 테스트가 등록한 규칙(작업 → 응답 또는 응답 함수)에 따라 답한다. 받은 프롬프트를 모두 기록한다 |
| `FakeEmbeddings` | `OpenAIEmbeddings` | `Embeddings` 상속. 문자 2-gram을 해시해 고정 차원(256) 벡터를 만들고 정규화한다. 글자가 많이 겹치는 텍스트끼리 가깝다 → 유사도 · MMR 차이를 결정적으로 재현 |
| `FakeHttpSession` | `requests.Session` | URL · 파라미터별 응답(JSON, 상태 코드, 헤더)을 순서대로 돌려주고, 보낸 요청(헤더 포함)을 기록한다 |
| `FakeClock` / `fake_sleep` | `time.monotonic`, `time.sleep` | 실제로 기다리지 않고 기다린 시간을 기록한다 (NF2006 호출 간격 검증) |

### 10.4 공통 픽스처 (`tests/conftest.py`)

- **네트워크 차단**: `live` 마커가 없는 테스트에서 `socket.socket.connect`를 막는다. 실수로 실제 API를 부르면 즉시 실패한다.
- `tmp_settings`: 임시 폴더를 가리키는 설정(Chroma · raw · manifest 경로).
- `movies_small`: 합성 영화 12편 (같은 제목 2편, 감독 빈 목록 1편, 한국 영화 4편 포함).
- `wiki_small`: 합성 위키 문서 (여러 영화가 공유하는 문서 1건, 동명 동화 문서 1건, 200자 미만 문서 1건 포함).
- 환경변수 격리: `GMS_API_KEY` 등을 테스트마다 지우거나 가짜 값으로 둔다.
- Chroma는 테스트마다 `tmp_path`에 새 `PersistentClient`를 만든다(프로세스 안 공유 상태 방지).

### 10.5 CI (GitHub Actions, `.github/workflows/ci.yml`)

| 단계 | 명령 | 실패 조건 |
|---|---|---|
| 설치 | `pip install -r requirements.txt -r requirements-dev.txt` (F2013 · F2016 도입 후 `-r requirements-advanced.txt` 추가) | 설치 실패 |
| 린트 | `ruff check .` / `ruff format --check .` | 위반 |
| 테스트 | `pytest --junitxml=reports/junit.xml` (`not live`가 기본) | 실패 1건 이상 |
| 결과 보관 | `reports/junit.xml`을 아티팩트로 업로드 | — |

- 트리거: `pull_request`(대상 `main`), `push`(`main`). 러너 `ubuntu-latest`, Python 3.12.
- 워크플로에는 **비밀 값을 넣지 않는다.** GMS 키 없이 통과해야 한다.
- `main` 브랜치 보호: CI 통과를 머지 조건으로 설정한다(저장소 설정, 수동 1회).
