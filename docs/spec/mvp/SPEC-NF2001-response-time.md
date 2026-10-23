# SPEC-NF2001 응답 시간

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2001** 응답 시간 (성능) |
| 구분 | MVP (비기능) |
| 상태 | Draft |
| 담당 모듈 | `movielab/services/qa.py`(단계별 시간 측정), `scripts/measure_latency.py` |
| 선행 SPEC | SPEC-F2009, SPEC-NF2002 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 대표 질문에 대한 전체 처리 시간이 사용에 지장이 없어야 한다.

## 2. 목표 (가정 A-10)

| 경우 | 목표 (대표 질문 Q1~Q5 중앙값) | 근거 |
|---|---|---|
| 이미 수집한 질문 (캐시 적중) | **10초 이하** | LLM 호출 1회(P3) + 임베딩 1회 + 로컬 검색 |
| 처음 묻는 질문 (수집 포함) | **45초 이하** | P1 · P2 · P3 3회 + 위키 호출(간격 1초 × 약 10~20회) + 임베딩 |

목표를 넘으면 "실패"가 아니라 원인을 설계문서에 기록하고 개선안을 낸다(호출 간격 · 검색어 수 · 문서 수 조정). 목표 값을 바꾸려면 이 SPEC을 먼저 고친다.

## 3. 상세 명세

### 3.1 측정

- `AnswerResult.timings: dict[str, float]` — `collect`, `retrieve`, `generate`, `total` (초). 하위 단계(`extract_queries`, `search`, `fetch`, `index`)는 `CollectReport.timings`.
- 측정은 `time.perf_counter()`. 서비스 계층에서 단계를 감싸 잰다.
- 로그 `INFO`에 `timings`를 남긴다. 화면에는 상태 상자 라벨에 총 시간만 보인다(`완료 (12.3초)`).
- `python -m scripts.measure_latency --questions docs/verification/questions.json [--runs 3]`
  - 각 질문을 처음(캐시 비움) 1회 + 캐시 적중 `runs`회 실행해 표로 출력하고 `docs/verification/latency.md`에 저장한다.
  - 실제 GMS · 위키백과를 쓰므로 로컬에서만 실행한다.

### 3.2 성능을 해치지 않기 위한 규칙

- 서비스 객체(LLM 클라이언트, Chroma 클라이언트, 그래프)는 앱 수명 동안 한 번만 만든다(`st.cache_resource`).
- 영화 목록 로드는 캐시한다(`st.cache_data`).
- 캐시 적중 경로에서는 외부 수집 호출 · `sleep`이 0회다(NF2002 연계).
- 임베딩은 배치로 보낸다(F2002, F2005).

## 4. 가정

| ID | 내용 |
|---|---|
| A-10 | 목표 시간 10초 / 45초 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2001-01 | 모든 답변 결과에 단계별 소요 시간이 기록된다 | V4.7-1 |
| AC-NF2001-02 | 캐시 적중 경로에서 외부 수집 호출과 대기(`sleep`)가 0회다 | V4.7-1 |
| AC-NF2001-03 | 대표 질문의 실제 처리 시간을 측정한 표가 있고, 목표와 비교되어 있다 | V4.7-1 |
| AC-NF2001-04 | 가짜 의존성으로 돌린 전체 파이프라인(수집 포함)이 2초 안에 끝난다 — 코드 자체의 불필요한 대기를 잡는 회귀 테스트 | V4.7-1 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2001-01 | 단위 | 가짜 의존성으로 `ask` | `timings`에 `collect`, `retrieve`, `generate`, `total` 키, 모두 ≥ 0 | 01 | `tests/unit/test_qa_service.py` |
| TC-NF2001-02 | 통합 | 같은 질문 두 번째 `ask` | `FakeHttpSession` 요청 0, `fake_sleep` 호출 0 | 02 | `tests/integration/test_cache_path.py` |
| TC-NF2001-03 | 통합 | 가짜 의존성 전체 흐름 (`fake_sleep` 사용) | 실제 경과 < 2초 | 04 | 〃 |
| TC-NF2001-04 | live | Q1 처음 / 두 번째 | 두 번째 `total` ≤ 10초 (실패 시 경고로 기록) | 03 | `tests/live/test_live_latency.py` |
| TC-NF2001-05 | 수동 | `scripts.measure_latency` 실행 | `docs/verification/latency.md` 생성, 목표 대비 표 | 03 | 문서 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-1 | 측정 표 | `docs/verification/latency.md` |

## 8. 범위 밖

- 동시 사용자 부하 시험.
