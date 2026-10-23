# SPEC-F2014 MMR 검색 적용

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2014** MMR 검색 적용 (검색 · 심화) |
| 구분 | 심화 |
| 상태 | Draft |
| 담당 모듈 | `movielab/rag/retriever.py`, `scripts/compare_retrieval.py` |
| 선행 SPEC | SPEC-F2006 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 유사도 검색 대신 MMR을 적용하여 근거의 다양성을 확보한다.

명세서 3장 세부 조건:
- ◆ 검색 결과를 넉넉히 가져온 뒤 다양성을 고려하여 근거를 선별해야 한다.
- ◆ 내용이 겹치는 청크가 근거에 몰리지 않아야 한다.
- ◆ 유사도 검색과 MMR 검색의 결과 차이를 확인할 수 있어야 한다.

## 2. 상세 명세

### 2.1 동작

- `settings.retrieval.search_type == "mmr"`이면 외부 청크 검색을 `max_marginal_relevance_search(query, k=top_k, fetch_k=mmr_fetch_k, lambda_mult=mmr_lambda, filter={"movie_id": …})`로 바꾼다.
- 메타 청크 고정 포함 · 병합 · 중복 제거 · 번호 부여(SPEC-F2006)는 그대로다.
- 기본값 `search_type = "similarity"`(MVP 동작 유지). MMR은 설정으로 켠다. 검증 후 기본값을 바꾸려면 이 SPEC과 00-product-overview §7을 고친다.
- MMR 결과의 `score`는 관련도 점수를 따로 계산해 채운다(표시 · 비교용).

### 2.2 비교 도구

```text
python -m scripts.compare_retrieval --movie-id 157336 --question "<Q1>" [--top-k 4 --fetch-k 20 --lambda 0.5]
```

출력(그리고 `docs/verification/retrieval_compare/<movie_id>.md` 저장):

| 순위 | 유사도: 문서 제목 · 청크 순번 · 점수 | MMR: 문서 제목 · 청크 순번 · 점수 |
|---|---|---|

+ 요약 지표: 서로 다른 문서 수, 근거 쌍 평균 코사인 유사도(낮을수록 다양), 두 목록의 겹침 수.

## 3. 가정

| ID | 내용 |
|---|---|
| A-09 | `fetch_k = 20`, `lambda_mult = 0.5` (명세서 예시는 30건 중 10건. Top-k 4에 맞춰 5배로 둠) |

## 4. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2014-01 | 설정 하나로 유사도 / MMR을 바꿀 수 있고, MMR은 `fetch_k`개를 가져와 `top_k`개를 고른다 | V4.5-2 |
| AC-F2014-02 | 거의 같은 내용의 청크가 여럿일 때 MMR 결과에는 그중 하나만(또는 더 적게) 들어간다 | V4.5-2 |
| AC-F2014-03 | 같은 질문에 대한 두 방식의 근거 목록 차이를 표로 확인할 수 있다 | V4.5-2 |
| AC-F2014-04 | MMR에서도 메타 청크는 `[근거 1]`이고 다른 영화 청크는 섞이지 않는다 | — |
| AC-F2014-05 | (필수 구현과 비교) 대표 질문 3개 이상의 비교 결과가 설계문서에 있다 | 4.8 |

## 5. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2014-01 | 통합 | `FakeEmbeddings` + 거의 같은 청크 3개 + 다른 주제 청크 3개, `top_k=3` | 유사도: 중복 청크가 2개 이상 / MMR: 중복 청크 1개 이하, 서로 다른 문서 수 증가 | 01, 02 | `tests/integration/test_mmr.py` |
| TC-F2014-02 | 통합 | MMR 모드 | `evidences[0]`이 메타, 외부 근거 모두 해당 `movie_id` | 04 | 〃 |
| TC-F2014-03 | 단위 | 설정 `search_type: "mmr"` / 오타 `"mrr"` | 로드 성공 / `SettingsError` | 01 | `tests/unit/test_config.py` |
| TC-F2014-04 | 통합 | `compare_retrieval` 실행(가짜) | 표 파일 생성, 요약 지표 3종 포함 | 03 | `tests/integration/test_scripts.py` |
| TC-F2014-06 | live | Q1 · Q2를 similarity / MMR로 검색 | MMR Top-4에 Q1 「인터스텔라」, Q2 「명량해협」 청크 포함 (SPEC-F2007 §7.1 관찰) | 05 | `tests/live/test_live_mmr.py` |
| TC-F2014-05 | 수동 | Q1 · Q2 · Q4 비교 실행 | 표와 해석을 설계문서에 기록 | 05 | 문서 |

## 6. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.5-2 | 비교 표 | `docs/verification/retrieval_compare/` + 설계문서 |

## 7. 범위 밖

- 하이브리드(키워드 + 벡터) 검색, 재순위(reranker).
