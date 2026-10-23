# SPEC-F2013 프론트엔드 직접 구현 (HTML · CSS · JavaScript)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2013** 프론트엔드 직접 구현 (UI · 심화) |
| 구분 | 심화 |
| 상태 | In Progress |
| 담당 모듈 | `movielab/api/server.py`, `movielab/api/schemas.py`, `web/index.html`, `web/app.js`, `web/style.css` |
| 선행 SPEC | MVP 전체 (특히 F2009~F2012, NF2004) |
| 관련 ISSUE | #23 |

## 1. 요구사항 원문

> HTML, CSS, JavaScript로 사용자 화면을 구현한다.

명세서 3장 세부 조건:
- ◆ 화면을 HTML, CSS, JavaScript로 구현해야 한다.
- ◆ 화면과 서버를 분리하고 요청 · 응답 형식을 정의해야 한다.
- ◆ 질문 입력, 답변 표시, 근거 문서 표시 기능을 모두 제공해야 한다.

## 2. 방침

- Streamlit 화면(MVP)은 그대로 둔다. 웹 화면은 **같은 `services`를 쓰는 두 번째 UI**다. RAG 파이프라인 코드는 바꾸지 않는다.
- 서버: FastAPI(`fastapi==0.141.1`, `uvicorn[standard]==0.52.4`, `pydantic==2.13.5`). 정적 파일 `web/`을 `/`에서 제공한다.
- 화면: 프레임워크 없는 HTML · CSS · JS(ES 모듈). 빌드 단계 없음. 외부 CDN을 쓰지 않는다.
- 의존성: 위 세 개는 `requirements-advanced.txt`(01-architecture §1). 테스트의 `fastapi.testclient.TestClient`가 요구하는 `httpx==0.28.1`은 `requirements-dev.txt`에 더한다(A-26). CI는 세 파일을 모두 설치한다.
- 서버 조립: `create_app(services)`가 앱을 만든다. 서비스는 주입받고(테스트는 가짜 서비스), 실제 실행 `python -m movielab.api.server`만 `container.build_services`를 쓴다. 기본 주소 `127.0.0.1:8000`(로컬 전용, A-27).
- 입력 길이 상한 1,000자는 `settings.ui.max_input_chars`, 영화 검색 기본 건수 50은 `settings.ui.movie_search_limit`에서 읽는다.
- 진행 단계 문구는 Streamlit과 같은 `messages.PROGRESS`를 쓴다(공용 함수 `messages.progress_text`).

## 3. API 명세 (요청 · 응답 형식)

모든 응답은 JSON(UTF-8). 스키마는 `movielab/api/schemas.py`의 pydantic 모델로 정의하고 `/docs`(OpenAPI)로 확인한다.

| 메서드 · 경로 | 요청 | 응답 | 대응 기능 |
|---|---|---|---|
| `GET /api/health` | — | `{api_key_configured: bool, index: {meta: int, docs: int}}` | F2012 |
| `GET /api/movies?q=&limit=50` | 제목 부분 검색 | `[{movie_id, title, year, genres}]` | F2009 |
| `POST /api/ask` | `{movie_id, question}` | `AnswerResponse` | F2006~F2008 |
| `POST /api/ask/stream` | `{movie_id, question}` | NDJSON 스트림: `{"type":"stage","stage":"search","message":"…"}` … 마지막 `{"type":"result","data":AnswerResponse}` | F2012 진행 상태 |
| `POST /api/guide` | `{movie_id}` | `GuideResponse` | F2010 |
| `POST /api/factcheck` | `{movie_id, claim}` | `FactCheckResponse` | F2010 |
| `POST /api/explore` | `{condition}` | `{items: [{movie_id, title, year, genres, director, reason}]}` | F2011 |

```jsonc
// AnswerResponse
{
  "answer": "블랙홀은 … [근거 2]",
  "citations": [
    {"n": 1, "source_type": "영화 메타데이터", "title": "인터스텔라 (2014)", "url": "https://www.themoviedb.org/movie/157336", "license": null},
    {"n": 2, "source_type": "위키백과", "title": "블랙홀", "url": "https://ko.wikipedia.org/wiki/…", "license": "CC BY-SA 4.0"}
  ],
  "uncited": false,
  "not_found": false,
  "notices": [{"code": "SOURCE_FALLBACK", "message": "…"}],
  "collected_titles": ["인터스텔라", "블랙홀"],
  "timings": {"total": 8.2}
}
```

```jsonc
// GuideResponse
{"markdown": "## 제작 배경 …", "citations": [...], "uncited": false, "notices": [...]}
// FactCheckResponse
{"claim": "…", "verdict": "사실" | "거짓" | "확인 불가", "reason": "…", "citations": [...], "notices": [...]}
// ExploreResponse
{"items": [...], "candidates": 20, "message": "조건에 맞는 영화를 찾지 못했습니다 …" | null}
```

- `citations`는 답변에 실제로 인용된 근거만(F2008). `notices`는 수집 안내(`SOURCE_FALLBACK`)와 외부 근거 없음(`NO_EXTERNAL_DOCS`)을 `messages`의 문구로 담는다.
- 스트림: 시작 전 검사(키 · 색인 · 입력)에 걸리면 스트림 없이 아래 오류 응답을 준다. 스트림 도중 실패하면 마지막 줄로 `{"type":"error","error":{code,message}}`를 보낸다.

**오류 응답** (NF2004): HTTP 상태 + `{"error": {"code": "API_KEY_MISSING" | "INDEX_EMPTY" | "ITEM_NOT_INDEXED" | "BAD_REQUEST" | "INTERNAL", "message": "<사용자용 문구>"}}`.
traceback · 예외 메시지 · 프롬프트는 응답에 넣지 않는다. 입력 검증 실패(빈 질문, 1,000자 초과, 없는 `movie_id`)는 400 + `BAD_REQUEST`.
상태 코드: `API_KEY_MISSING` · `INDEX_EMPTY` 503(키 · 색인이 필요한 경로만, `health` · `movies`는 키 없이 동작), `ITEM_NOT_INDEXED` 409, `INTERNAL` 500.
위 다섯 코드에 없는 안내 오류(`SOURCE_UNAVAILABLE` 등)는 코드 `INTERNAL`, 문구는 그 안내 오류의 문구로 보낸다(A-28).

## 4. 화면 명세 (`web/`)

| 영역 | 기능 |
|---|---|
| 왼쪽 패널 | 영화 검색 입력 + 결과 목록(`제목 (연도)`), 색인 건수, 출처 고지 |
| 상단 메뉴 | 질문하기 · 관람 가이드 · 사실 판정 · 조건 탐색 |
| 질문하기 | 영화별 대화 기록(`localStorage` 아님, 페이지 메모리 + `sessionStorage`), 질문 입력, 진행 상태 줄(스트림 단계 표시), 답변 + 인용 근거 목록(번호 · 출처 유형 · 제목 · 원문 링크 · 라이선스), 인용 없음 안내 |
| 관람 가이드 · 사실 판정 · 조건 탐색 | Streamlit과 같은 기능. 조건 탐색 카드 클릭 → 그 영화 선택 + 질문하기로 이동 |
| 안내 | `/api/health` 결과로 키 없음 · 색인 없음 배너 |

- 답변 텍스트는 `textContent`로 넣는다(HTML 주입 방지). 근거 링크는 `rel="noopener noreferrer"`, `target="_blank"`.
- 휴대폰 너비(360px)에서도 쓸 수 있게 한 열로 접힌다.

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2013-01 | 웹 화면이 HTML · CSS · JS만으로 동작한다(Streamlit 없이) | V4.5-1 |
| AC-F2013-02 | 화면과 서버가 분리되고, 요청 · 응답 형식이 스키마와 OpenAPI 문서로 정의되어 있다 | V4.5-1 |
| AC-F2013-03 | 질문 입력 → 답변 표시 → 인용 근거 표시가 모두 된다 | V4.5-1 |
| AC-F2013-04 | 오류 응답에 내부 정보가 없다 | V4.7-4 |
| AC-F2013-05 | 진행 상태가 스트림 단계로 표시된다 | V4.4-4 |
| AC-F2013-06 | (필수 구현과 비교) Streamlit과 웹 화면의 기능 대응표가 검증 문서에 있다 | 4.8 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2013-01 | 통합 | `TestClient` + 가짜 서비스 `POST /api/ask` | 200, `AnswerResponse` 스키마, 인용 근거만 `citations`에 | 02, 03 | `tests/integration/test_api.py` |
| TC-F2013-02 | 통합 | `POST /api/ask/stream` | 줄 단위 JSON, `stage` 여러 개 후 `result` 하나 | 05 | 〃 |
| TC-F2013-03 | 통합 | 서비스가 예외 | 500, `{"error":{"code":"INTERNAL",…}}`, 본문에 `Traceback` 없음 | 04 | 〃 |
| TC-F2013-04 | 통합 | 키 없음 · 색인 없음 · 빈 질문 · 없는 영화 | 각각 정의된 코드 | 02 | 〃 |
| TC-F2013-05 | 통합 | `GET /` · `/app.js` · `/style.css` | 200, `index.html`에 질문 입력 · 답변 · 근거 영역 요소 ID 존재 | 01 | 〃 |
| TC-F2013-06 | 단위 | `GET /openapi.json` | 모든 경로와 스키마 존재 | 02 | 〃 |
| TC-F2013-07 | 수동 | 브라우저에서 Q1 질문, 휴대폰 너비 확인 | 화면 캡처 | 01, 03 | 스크린샷 |
| TC-F2013-08 | 수동 | Streamlit과 웹 화면에서 F2009~F2012 기능을 하나씩 실행 | 기능 대응표(기능 · Streamlit · 웹 · 차이)를 검증 결과 문서에 기록 | 06 | `docs/verification/F2013_web_vs_streamlit.md` (제출 시 `03_검증결과.md`로 옮김) |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.5-1 | 웹 화면에서 질문 · 답변 · 근거 캡처, OpenAPI 화면 | `docs/verification/screenshots/V4.5-1_web*.png` |
| 필수 구현과 비교 | Streamlit vs 웹 기능 대응표 | `docs/verification/F2013_web_vs_streamlit.md` (제출 시 `03_검증결과.md`로 옮김) |

## 8. 범위 밖

- 인증, 배포(로컬 실행만), 대화 기록 서버 저장.
