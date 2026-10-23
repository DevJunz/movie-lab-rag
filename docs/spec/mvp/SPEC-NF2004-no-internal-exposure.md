# SPEC-NF2004 내부 정보 비노출

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2004** 내부 정보 비노출 (보안) |
| 구분 | MVP (비기능) |
| 상태 | Draft |
| 담당 모듈 | `movielab/ui/streamlit_app.py`, `movielab/api/server.py`(F2013), `movielab/core/messages.py`, `.streamlit/config.toml`, 로깅 설정 |
| 선행 SPEC | SPEC-F2012, SPEC-NF2003 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 화면에 API 키, 전체 프롬프트, 오류 추적 정보를 노출하지 않아야 한다.

## 2. 상세 명세

### 2.1 금지 목록과 대응

| 노출 금지 | 대응 |
|---|---|
| API 키 (전체 · 일부 · 길이) | 화면은 키의 "있음/없음"만 판단에 쓰고 표시하지 않는다. 설정 객체 `repr` 가림(NF2003) |
| 전체 프롬프트 | 프롬프트는 `DEBUG` 로그에만. 화면의 "수집 상세"에는 검색어 · 후보 제목 · 사유만 보인다. 근거 미리보기는 근거 본문 200자까지 |
| 오류 추적 정보(traceback, 예외 메시지, 파일 경로) | UI · API 최상위에서 예외를 잡아 `core/messages`의 사용자용 문구만 보인다. traceback은 `logs/movielab.log`에만 |
| Streamlit 기본 오류 화면 | `.streamlit/config.toml`에 `[client] showErrorDetails = "none"` (Streamlit 1.62의 허용 값으로 맞춤). 그래도 새는 예외에 대비해 모든 사용자 동작 처리 함수를 `safe_run` 데코레이터로 감싼다 |
| GMS 주소 · 내부 경로 | 안내 문구에 변수 **이름**(`GMS_API_KEY`)은 쓰되 값은 쓰지 않는다 |

### 2.2 오류 처리 구조

```python
# movielab/ui/streamlit_app.py
def safe_run(fn):
    """사용자 동작 처리 함수를 감싼다. 안내용 예외는 해당 문구로, 그 밖의 예외는 GENERIC_ERROR로 바꾼다."""
```

- `MovieLabUserError` 하위 예외(`MissingApiKeyError`, `IndexEmptyError` …) → 해당 안내 코드 문구.
- 그 밖의 `Exception` → `GENERIC_ERROR` 문구 + `logger.exception(...)`(로그 파일에 traceback).
- API 서버(F2013)도 같은 규칙: 응답 본문은 `{"error": {"code", "message"}}`만. FastAPI 기본 500 응답을 전역 예외 처리기로 바꾼다.

### 2.3 로그

- `logs/movielab.log` (회전, `.gitignore`). 키는 가린다(NF2003).
- `INFO`: 단계 · 소요 시간 · 수집 문서 제목. `DEBUG`: 프롬프트 · LLM 원문 출력. 기본 레벨은 `INFO`.

## 3. 가정

없음.

## 4. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2004-01 | 서비스에서 예외가 나도 화면에 traceback · 예외 메시지 · 파일 경로가 보이지 않고 사용자용 문구만 보인다 | V4.7-4 |
| AC-NF2004-02 | 화면 어디에도 API 키 값이 보이지 않는다 | V4.7-4 |
| AC-NF2004-03 | 화면에 프롬프트 템플릿 문구(`[작업:` 머리표, 규칙 문장)가 보이지 않는다 | V4.7-4 |
| AC-NF2004-04 | traceback은 로그 파일에 남는다 | — |
| AC-NF2004-05 | `.streamlit/config.toml`이 오류 상세 표시를 끈다 | V4.7-4 |

## 5. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2004-01 | 통합 | `AppTest`: 가짜 서비스가 `ValueError("C:\\secret\\path sk-test-123")` | 화면 텍스트에 `Traceback`, `ValueError`, `secret`, `sk-test` 없음, `GENERIC_ERROR` 있음 | 01 | `tests/integration/test_ui_no_leak.py` |
| TC-NF2004-02 | 통합 | `AppTest`: 가짜 키 `sk-test-abcdef…` 설정 후 모든 페이지 렌더 | 화면 전체 텍스트에 키 문자열 없음 | 02 | 〃 |
| TC-NF2004-03 | 통합 | `AppTest`: 질문 처리 후 화면 텍스트 | `[작업:` · `규칙:` 문자열 없음 | 03 | 〃 |
| TC-NF2004-04 | 단위 | `safe_run`이 예외를 잡을 때 로그 | `caplog`에 traceback 기록 | 04 | `tests/unit/test_safe_run.py` |
| TC-NF2004-05 | 단위 | `.streamlit/config.toml` 파싱 | `client.showErrorDetails`가 끔 값 | 05 | `tests/unit/test_streamlit_config.py` |
| TC-NF2004-06 | 수동 | `.env` 없이 실행, 일부러 오류 발생 | 화면 캡처에 내부 정보 없음 | 01, 02 | 스크린샷 |

## 6. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-4 | 오류 상황 화면 캡처 | `docs/verification/screenshots/V4.7-4_error.png` |

## 7. 범위 밖

- 접근 제어 · 인증.
