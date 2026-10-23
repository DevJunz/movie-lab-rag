# SPEC-F2015 RAG 전후 품질 비교

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2015** RAG 전후 품질 비교 (품질 · 심화) |
| 구분 | 심화 |
| 상태 | In Progress |
| 담당 모듈 | `scripts/compare_rag.py`, `movielab/prompts.py`(B1: RAG 없는 답변), `docs/verification/questions.json` |
| 선행 SPEC | SPEC-F2007, SPEC-F2008 |
| 관련 ISSUE | #21 |

## 1. 요구사항 원문

> RAG 사용 전후의 답변을 비교하여 차이를 정리한다.

명세서 3장 세부 조건:
- ◆ 대표 질문에 대해 RAG 사용 전후의 답변을 확보해야 한다.
- ◆ 사실 정확성과 근거 제시 여부로 차이를 정리해야 한다.
- ◆ 비교 결과는 문서로 작성하여 제출해야 한다.

명세서 4.6:
- 대표 질문을 5개 이상 정한다. 근거 없이 답하면 틀리기 쉬운 질문으로 고른다.
- 같은 질문을 RAG 없이 한 번, 근거를 붙여 한 번 답하게 하고 두 답을 나란히 기록한다.
- 사실 정확성, 근거 제시 여부, 모르는 것을 모른다고 답하는지 세 기준으로 비교한다.

## 2. 상세 명세

### 2.1 대표 질문 (`docs/verification/questions.json`)

[00-product-overview.md §3](../00-product-overview.md#3-대표-질문)의 Q1~Q6을 그대로 쓴다(5개 이상 + 확인 불가 질문 1개).
각 항목에 `reference_facts`(위키 문서에서 확인한 정답 요지와 출처 URL)를 사람이 채워 넣는다 — 정확성 판정 기준.
키는 모든 항목에 있어야 하고(빈 목록 허용 — Q6처럼 정답이 없는 질문), 항목마다 `fact` · `source_url`을 가진다.

```json
[{"id": "Q2", "movie_id": "282631", "question": "명량 해전에서 조선 수군의 배는 실제로 몇 척이었나?",
  "reference_facts": [{"fact": "…", "source_url": "https://ko.wikipedia.org/wiki/…"}]}]
```

### 2.2 실행 (`python -m scripts.compare_rag [--questions …] [--out docs/deliverables/04_RAG_전후_비교.md]`)

| 조건 | 방법 |
|---|---|
| RAG 없음 | 프롬프트 B1: `[작업: 직접 답변]` + 영화 제목 (연도) + 질문. 근거 블록 없음. 같은 모델 · `temperature=0` |
| RAG 사용 | `QAService.ask`(수집 → 그래프 → 인용) 그대로 |

- 원본 출력은 `reports/compare_rag/<날짜시각>.json`에 남기고(`.gitignore`), 표는 마크다운으로 쓴다(`--raw-dir`로 바꿀 수 있다).
- B1 프롬프트(`movielab/prompts.py` `DIRECT_ANSWER`)는 역할 · `{item_label}: 제목 (연도)` · 질문 · "한국어로 답하라"만 담는다. 근거 블록과 확인 불가 규칙을 넣지 않는다 — RAG 없는 기본 상태를 재기 위해서다.
- 제목 (연도)는 `Catalog.get(movie_id).display_name`. 카탈로그에 없는 `movie_id`는 그 질문을 건너뛰고 표에 "항목 없음"으로 적는다.
- 같은 모델 · 온도: 두 조건 모두 `services.llm`(설정 `models.chat` · `models.temperature`)을 쓴다. 실험 조건 절에 두 값을 적는다.
- 답변 표 칸 안의 줄바꿈은 `<br>`, `|`는 `/`로 바꾼다.
- 평가 열은 스크립트가 빈칸으로 만들고 **사람이 채운다**: 사실 정확성(정확 / 부분 / 틀림), 근거 제시(있음 / 없음), 모르면 모른다고 답함(예 / 아니오 / 해당 없음).
- 근거 제시 열은 자동 보조값을 제공한다: RAG 답변의 인용 수, RAG 없는 답변의 출처 언급 여부.

### 2.3 보고서 형식 (`docs/deliverables/04_RAG_전후_비교.md`)

1. 실험 조건(모델, 날짜, 설정값: 청크 · Top-k · 검색 방식)
2. 질문별 비교 표: 질문 | RAG 없음 답변 | RAG 답변(+인용) | 정답 요지 | 세 기준 평가
3. 요약: 기준별 집계(예: 정확 2/6 → 5/6), 관찰(환각 사례, 확인 불가 응답), 한계

## 3. 가정

| ID | 내용 |
|---|---|
| — | 정확성 판정은 사람이 `reference_facts` 기준으로 한다(자동 채점 없음) |

## 4. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2015-01 | 대표 질문이 5개 이상이고 근거 없이 틀리기 쉬운 질문이다 | V4.6-1, V4.5-3 |
| AC-F2015-02 | 질문마다 RAG 없음 / 사용 답변이 나란히 기록된다 | V4.6-2, V4.5-3 |
| AC-F2015-03 | 사실 정확성 · 근거 제시 · 모르면 모른다고 답함 세 기준으로 평가되어 있다 | V4.6-3 |
| AC-F2015-04 | 비교 결과 문서가 제출물에 포함된다 | V4.6-4 |
| AC-F2015-05 | 두 조건은 같은 모델 · 온도로 실행된다 | — |

## 5. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2015-01 | 단위 | `questions.json` 검사 | 5개 이상, 필수 키 존재, `movie_id`가 `movies.json` 형식(문자열) | 01 | `tests/unit/test_questions.py` |
| TC-F2015-02 | 통합 | 가짜 LLM으로 `compare_rag` 실행 | 질문 수만큼 행, 두 답변 열, 평가 열 3개(빈칸), 실험 조건 절 | 02, 03 | `tests/integration/test_compare_rag.py` |
| TC-F2015-03 | 단위 | B1 프롬프트 | 근거 블록 없음, `[작업: 직접 답변]` | 05 | `tests/unit/test_prompts.py` |
| TC-F2015-04 | live / 수동 | 실제 GMS로 실행 후 평가 기입 | 보고서 완성 | 03, 04 | `docs/deliverables/04_RAG_전후_비교.md` |

## 6. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.5-3, V4.6 | 비교 보고서 | `docs/deliverables/04_RAG_전후_비교.md` |

## 7. 범위 밖

- LLM 자동 채점(LLM-as-judge). 통계적 유의성 검정.
