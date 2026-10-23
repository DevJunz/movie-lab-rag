# SPEC-NF2003 API 키 관리

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2003** API 키 관리 (보안) |
| 구분 | MVP (비기능) |
| 상태 | Draft |
| 담당 모듈 | `movielab/config.py`, `movielab/providers.py`, `.env.example`, `.gitignore`, `tests/unit/test_secrets.py` |
| 선행 SPEC | SPEC-NF2005 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> API 키는 환경변수로 관리하고 소스코드에 포함하지 않아야 한다.

## 2. 도메인 표현 (Movie Lab)

GMS 키와 주소, 위키백과 연락처는 `.env`에만 둔다. 저장소에는 값이 빈 `.env.example`만 올린다.

## 3. 상세 명세

### 3.1 로드

- `python-dotenv`의 `load_dotenv()`는 **`movielab.config.load_settings()` 안에서 한 번만** 부른다. 이미 설정된 환경변수를 덮어쓰지 않는다(`override=False`).
- 비밀 값은 `Settings.secrets`(`gms_api_key`, `gms_base_url`, `wiki_contact`)로만 꺼낸다. `__repr__` · 로그 출력 시 `***`로 가린다.
- `providers.make_chat_model(settings)` · `make_embeddings(settings)`는 키가 없으면 `MissingApiKeyError`를 던진다(F2012 안내로 연결).

### 3.2 저장소 보호

- `.gitignore`: `.env`, `.env.*`(단 `!.env.example`), `/data/`, `/logs/`, `/reports/`, `/영화도메인_데이터_배포용/`, `/prd.pdf`, `/rag_project_briefing.html`, `*.zip`.
  데이터 · 산출물 경로는 **앞에 `/`를 붙여 저장소 루트로 고정**한다. `data/`라고 쓰면 `movielab/data/` 패키지까지 무시된다(개발 기록 참고).
- `.env.example`:

```text
# SSAFY GMS (OpenAI 호환) — 값은 GMS 안내 페이지에서 확인
GMS_API_KEY=
GMS_BASE_URL=
# 위키백과 User-Agent 연락처 (이메일 또는 저장소 URL) — NF2006
WIKI_CONTACT=
# 선택: LangSmith 추적 (기본 꺼짐)
LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
```

### 3.3 유출 검사 (CI에서 실행되는 테스트)

`tests/unit/test_secrets.py`가 Git이 추적하는 파일(`git ls-files`, Git이 없으면 저장소 전체)을 훑는다.

| 검사 | 기준 |
|---|---|
| 키 패턴 | `sk-[A-Za-z0-9_-]{20,}`, `(?i)(api[_-]?key\|secret\|token)\s*[:=]\s*["'][^"'\s]{16,}["']` 가 소스 · 문서 · 설정에 없음 |
| `.env` 추적 금지 | 추적 파일에 `.env`가 없음 |
| `.gitignore` | `.env`, `/data/`, `/영화도메인_데이터_배포용/`, `/prd.pdf` 항목이 있음 |
| `.env.example` | 모든 값이 비어 있거나 `false` |

- 예외 목록(테스트 코드의 가짜 키 `sk-test…` 등)은 `tests/unit/test_secrets.py` 안에 명시적으로 둔다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-02 | 변수 이름 `GMS_API_KEY`, `GMS_BASE_URL` |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2003-01 | 키 · 주소는 환경변수(`.env`)에서만 읽는다. 코드에 기본 키 값이 없다 | V4.7-3 |
| AC-NF2003-02 | 추적 파일에 키 패턴이 없고 `.env`가 추적되지 않는다 (CI에서 매번 검사) | V4.7-3 |
| AC-NF2003-03 | 키가 없으면 `MissingApiKeyError` → 안내 화면 (F2012) | V4.4-5 |
| AC-NF2003-04 | 설정 객체를 출력 · 로그해도 키가 가려진다 | V4.7-4 |
| AC-NF2003-05 | 제출 zip에 `.env`, `data/`, 제공 데이터 팩이 들어가지 않는다 | V4.7-3 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2003-01 | 단위 | 환경변수에 가짜 키를 넣고 `load_settings` | `secrets.gms_api_key`가 그 값 | 01 | `tests/unit/test_config.py` |
| TC-NF2003-02 | 단위 | 환경변수 없이 `make_chat_model` | `MissingApiKeyError` | 03 | `tests/unit/test_providers.py` |
| TC-NF2003-03 | 단위 | `repr(settings)`, 로그 레코드 | 키 원문 없음, `***` 있음 | 04 | `tests/unit/test_config.py` |
| TC-NF2003-04 | 단위 | 저장소 스캔 | 키 패턴 0건, `.env` 미추적, `.gitignore` 항목 존재 | 02, 05 | `tests/unit/test_secrets.py` |
| TC-NF2003-05 | 단위 | 스캐너에 `sk-` 키가 든 임시 파일을 넣음 | 검출됨 (스캐너 자체 검증) | 02 | 〃 |
| TC-NF2003-06 | 수동 | 제출 zip 목록 확인 | `.env` · `data/` · 데이터 팩 없음 | 05 | 제출 전 점검 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-3 | CI 결과(TC-NF2003-04 통과) + 제출 zip 목록 | 검증 결과 문서 |

## 8. 범위 밖

- 키 교체 자동화, 비밀 관리 서비스.
