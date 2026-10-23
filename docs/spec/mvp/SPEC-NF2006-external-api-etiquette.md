# SPEC-NF2006 외부 API 예절

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2006** 외부 API 예절 (품질) |
| 구분 | MVP (비기능) |
| 상태 | Done |
| 담당 모듈 | `movielab/data/wiki_api.py` (`WikiHttpClient`) |
| 선행 SPEC | SPEC-NF2005, SPEC-NF2003 |
| 관련 ISSUE | #5 |

## 1. 요구사항 원문

> 재시도와 호출 간격 규칙을 지키고, 출처가 요구하는 식별 정보(예: 위키백과 User-Agent 연락처)를 포함해야 한다.

## 2. 근거 규칙

- Wikimedia User-Agent 정책: 도구 이름 · 버전 · **연락처**(이메일 또는 URL)를 담은 User-Agent를 보낸다. 일반 라이브러리 기본값(`python-requests/x.y`)만 보내면 차단될 수 있다.
- MediaWiki API 예절: 요청은 **직렬**로 보낸다, `maxlag` 파라미터를 쓴다, 오류 · 지연 응답에는 기다렸다 재시도한다.

## 3. 상세 명세

### 3.1 User-Agent

```text
MovieLab/0.1 (+https://github.com/DevJunz/movie-lab-rag; contact: <WIKI_CONTACT>) python-requests/2.34.2
```

- `app_name` · `app_version`은 `settings.wiki`, 연락처는 `.env`의 `WIKI_CONTACT`(A-03). 저장소 URL은 `settings.wiki.project_url`.
- `WIKI_CONTACT`가 비어 있으면 **API를 호출하지 않는다**. `source=api`이면 `ExternalSourceUnavailableError`, `auto`이면 묶음으로 대체(F2004 §3.2).
- `Accept-Encoding: gzip`을 보낸다.

### 3.2 호출 간격 · 재시도 (가정 A-04)

| 규칙 | 값 | 설정 키 |
|---|---|---|
| 동시 요청 | 1 — **프로세스 전체에서 직렬**. 잠금과 마지막 요청 시각은 API 주소별로 공유하는 `RequestThrottle`이 가진다(Streamlit 세션 · 스레드가 여러 개여도 한 줄로 선다) | — |
| 최소 호출 간격 | 이전 요청 **시작** 후 1.0초 | `wiki.min_interval_sec` |
| 타임아웃 | 10초 | `wiki.timeout_sec` |
| `maxlag` | 5 | `wiki.maxlag` |
| 재시도 대상 | `requests`의 모든 요청 예외(연결 끊김 · 타임아웃 · 본문 수신 중 끊김 · 압축 오류 · 넘겨주기 과다) · HTTP 429 · 500 · 502 · 503 · 504 · **200인데 JSON이 아닌 본문**(점검 페이지 등) · 응답 본문 `error.code == "maxlag"` | — |
| 재시도 횟수 | 최대 3회 (첫 시도 포함 4번) | `wiki.max_retries` |
| 대기 | `Retry-After`가 **유효하면** 그 값(초 또는 HTTP 날짜, 최대 `wiki.max_retry_after_sec`=60초). 음수 · NaN · 해석 불가면 무시하고 `backoff_base × 2^시도` (1 · 2 · 4초) | `wiki.backoff_base_sec`, `wiki.max_retry_after_sec` |
| 재시도 안 함 | 404 → 빈 결과 `{}`. 그 밖의 4xx(400 · 403 …) → 즉시 `ExternalSourceUnavailableError`. 응답 본문의 `maxlag` 외 API 오류 코드도 즉시 오류 | — |
| 최종 실패 | `ExternalSourceUnavailableError`(안내 코드 `SOURCE_UNAVAILABLE`) → `auto`면 묶음 대체 | — |

- 호출 간격은 **재시도를 포함한 모든 요청**에 적용한다(백오프 대기가 간격보다 길면 추가 대기 없음).
- 시간 · 대기 함수(`clock`, `sleep`)는 생성자로 주입한다. 테스트는 `FakeClock` · `fake_sleep`으로 실제로 기다리지 않고 대기 시간을 검사한다.
- `Services.wiki_client`(container)가 클라이언트를 한 번만 만든다. 주입한 `http` 세션이 있으면 그것을 쓴다.
- 모든 요청은 성공 · 실패와 상관없이 로그에 `action`, 상태 코드(예외면 예외 이름), 소요 시간(주입된 시계 기준), 시도 번호를 남긴다(연락처는 남기지 않는다).
- 실제 `requests.Session`은 조립 지점(container)이 만든다. `WikiHttpClient`는 세션을 반드시 주입받는다.
- `Services.wiki_client`는 잠금 안에서 한 번만 만들고, 프로세스 공용 `RequestThrottle`을 쓴다.

### 3.3 인터페이스

```python
class WikiHttpClient:
    def __init__(self, settings, contact: str, session=None, clock=time.monotonic, sleep=time.sleep): ...
    def get(self, params: dict) -> dict: ...      # 공통 파라미터(format, formatversion, maxlag) 자동 추가
```

## 4. 가정

| ID | 내용 |
|---|---|
| A-03 | 연락처는 `WIKI_CONTACT` |
| A-04 | 간격 1.0초, 재시도 3회, 백오프 1 · 2 · 4초, `Retry-After` 최대 60초, 타임아웃 10초, `maxlag=5` |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2006-01 | 모든 위키 요청에 앱 이름 · 버전 · 연락처를 담은 User-Agent가 있다 | V4.7-6 |
| AC-NF2006-02 | 연락처가 없으면 위키 API 요청을 보내지 않는다 | V4.7-6 |
| AC-NF2006-03 | 연속 요청 사이 간격이 설정값 이상이다 | V4.7-6 |
| AC-NF2006-04 | 429 · 5xx · 연결 오류는 지수 백오프로 최대 3회 재시도하고, `Retry-After`가 있으면 따른다 | V4.7-6 |
| AC-NF2006-05 | 403 등 재시도 대상이 아닌 오류는 재시도하지 않는다 | V4.7-6 |
| AC-NF2006-06 | 모든 요청에 `maxlag`가 들어가고, `maxlag` 오류는 재시도한다 | V4.7-6 |
| AC-NF2006-07 | 요청은 직렬로만 나간다 | V4.7-6 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2006-01 | 단위 | `FakeHttpSession`이 받은 헤더 | `User-Agent`에 `MovieLab/0.1`과 연락처 포함 | 01 | `tests/unit/test_wiki_http.py` |
| TC-NF2006-02 | 단위 | 연락처 빈 값으로 `get` | 요청 0건, `ExternalSourceUnavailableError` | 02 | 〃 |
| TC-NF2006-03 | 단위 | `FakeClock`으로 요청 3번 연속 | 2 · 3번째 전에 `sleep`으로 간격 보충, 간격 ≥ 1.0 | 03 | 〃 |
| TC-NF2006-04 | 단위 | 응답 503, 503, 200 | 요청 3번, 대기 1 · 2초, 성공 | 04 | 〃 |
| TC-NF2006-05 | 단위 | 응답 429 + `Retry-After: 7` | 7초 대기 후 재시도 | 04 | 〃 |
| TC-NF2006-06 | 단위 | 응답 503 × 4 | 요청 4번 후 `ExternalSourceUnavailableError` | 04 | 〃 |
| TC-NF2006-07 | 단위 | 응답 403 | 요청 1번, 즉시 예외 | 05 | 〃 |
| TC-NF2006-08 | 단위 | 모든 요청 파라미터 | `maxlag=5`, `format=json`, `formatversion=2` | 06 | 〃 |
| TC-NF2006-09 | 단위 | 본문 `{"error":{"code":"maxlag"}}` 후 정상 | 재시도 후 성공 | 06 | 〃 |
| TC-NF2006-10 | 단위 | 요청이 나가는 순간 공유 잠금이 잡혀 있는지 (세션 훅으로 확인, 실제 시간 · 스레드 타이밍에 기대지 않음) | 매 요청마다 잠김 | 07 | 〃 |
| TC-NF2006-12 | 단위 | 200 + JSON 아닌 본문 반복 / 한 번 후 정상 | 재시도 후 `ExternalSourceUnavailableError` / 성공 | 04 | 〃 |
| TC-NF2006-13 | 단위 | `ChunkedEncodingError` · `ContentDecodingError` 후 정상 | 재시도해 성공 | 04 | 〃 |
| TC-NF2006-14 | 단위 | `Retry-After`: HTTP 날짜(10초 뒤) · `-5` · `nan` · `abc` | 10초 / 백오프 · 백오프 · 백오프 | 04 | 〃 |
| TC-NF2006-15 | 단위 | 같은 `RequestThrottle`을 쓰는 두 클라이언트의 연속 요청, container가 공용 throttle 사용 | 두 번째 요청 전 간격만큼 대기 / 같은 객체 | 03, 07 | 〃 |
| TC-NF2006-16 | 단위 | 성공 · 403 · API 오류 요청의 로그 | 상태 코드(또는 오류 코드) 포함, 연락처 미포함 | 01 | 〃 |
| TC-NF2006-11 | live | 실제 위키백과에 검색 1회 | 200 응답, 결과 ≥ 1 | 01 | `tests/live/test_live_wiki.py` |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-6 | 위 단위 테스트 결과 + 실제 수집 로그 일부(요청 간격 · User-Agent 앱 이름) | 검증 결과 문서 |

## 8. 범위 밖

- 다른 외부 API(PDF는 로컬 파일, F2016).
