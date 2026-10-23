# SPEC-F2006 근거 검색 및 병합

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2006** 근거 검색 및 병합 (검색 · 필수) |
| 구분 | MVP |
| 상태 | In Progress |
| 담당 모듈 | `movielab/rag/retriever.py` |
| 선행 SPEC | SPEC-F2002, SPEC-F2005 |
| 관련 ISSUE | #10 |

## 1. 요구사항 원문

> 두 컬렉션을 검색하여 병합하고 중복 청크를 제거한다. 검색할 근거 수(Top-k)는 설정으로 조정할 수 있어야 한다.

명세서 3장 세부 조건:
- ◆ 선택한 항목의 메타데이터 청크는 항상 근거에 포함해야 한다.
- ◆ 질문과의 의미 유사도로 외부 문서 청크를 검색해야 한다.
- ◆ 두 컬렉션의 검색 결과를 병합하고 중복 청크를 제거해야 한다.
- ◆ 검색할 근거 수(Top-k)는 설정으로 조정할 수 있어야 한다.

## 2. 도메인 표현 (Movie Lab)

선택한 영화의 메타 청크는 검색 없이 ID로 꺼내 항상 `[근거 1]`에 넣는다. 위키 청크는 그 영화로 범위를 좁혀(`movie_id` 필터) 질문과 의미가 가까운 Top-k개를 가져온다.

## 3. 상세 명세

### 3.1 동작 (`Retriever.retrieve(movie_id, query) -> list[Evidence]`)

1. **메타 청크**: `store.get_by_ids(meta, [movie_id])`. 없으면 `IndexEmptyError`(색인 0건) 또는 `ItemNotIndexedError`(해당 영화만 없음).
2. **외부 청크**: `wiki_docs`에서 `similarity_search_with_score(query, k=top_k, filter={"movie_id": movie_id})`.
   이 SPEC에서는 `search_type`으로 `"similarity"`만 허용한다(그 밖의 값은 시작할 때 `SettingsError`). MMR은 SPEC-F2014가 허용 값과 분기를 더한다.
3. **병합**: `[메타 청크] + [외부 청크(점수 순)]`.
4. **중복 제거**: ① 청크 ID가 같으면 하나만 남긴다. ② 공백을 정규화한 본문의 해시가 같으면(같은 내용이 다른 문서 ID로 들어온 경우) 먼저 나온 것만 남긴다.
5. **번호 부여**: 남은 순서대로 `n = 1, 2, …`. 메타 청크는 항상 `[근거 1]`.
6. 메타 근거의 제목은 `제목 (연도)`. 외부 근거의 `score`는 코사인 유사도(1 − 거리, 클수록 가깝다).
7. 결과 `Evidence`에는 `source_kind`, `source_type`, `title`, `url`, `license`, `score`를 채운다.

- 근거 총수 = 메타 1 + 외부 최대 `top_k`. `top_k`는 `settings.retrieval.top_k`(기본 4)에서만 읽는다.
- 외부 청크가 0개여도 예외가 아니다. 결과에 `no_external=True` 표시를 남겨 UI가 "관련 외부 문서를 찾지 못했습니다" 안내를 띄운다(F2012).

### 3.2 인터페이스

```python
class Retriever:
    def __init__(self, store: VectorStore, settings): ...
    def retrieve(self, movie_id: str, query: str) -> RetrievalResult: ...   # evidences, no_external
```

- 계층 규칙상 스크립트는 `Services.retriever(top_k=…)`(container)로 얻는다.

```text
python -m scripts.collect --movie-id 157336 --question "<Q1>" --show-evidence [--top-k 2]
  → 근거 번호 · 출처 유형 · 제목 · 점수 목록 (V4.3-1 비교용. --top-k는 설정을 일시적으로 덮어씀)
```

## 4. 가정

| ID | 내용 |
|---|---|
| D-04 | Top-k = 4 (사용자 확인) |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2006-01 | 질문 내용과 상관없이 선택 영화의 메타 청크가 항상 `[근거 1]`이다 | V4.3-4 |
| AC-F2006-02 | 외부 청크는 선택 영화의 `movie_id` 청크만 나온다 (다른 영화 문서가 섞이지 않는다) | — |
| AC-F2006-03 | 외부 청크는 질문과의 의미 유사도 순이다 | — |
| AC-F2006-04 | 같은 청크 ID · 같은 본문은 한 번만 나온다 | — |
| AC-F2006-05 | 설정 `top_k`를 바꾸면 외부 근거 수가 바뀐다(문서가 충분할 때 `top_k`개) | V4.3-1 |
| AC-F2006-06 | 외부 청크가 없으면 메타 근거 1개만 반환하고 `no_external=True` | V4.4-5 |
| AC-F2006-07 | 메타 색인이 비어 있으면 `IndexEmptyError` | V4.4-5 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2006-01 | 통합 | 메타와 무관한 질문으로 검색 | `evidences[0]`이 메타, `n == 1` | 01 | `tests/integration/test_retriever.py` |
| TC-F2006-02 | 통합 | 영화 A · B가 비슷한 문서를 가짐, A로 검색 | 외부 근거 전부 `movie_id == A` | 02 | 〃 |
| TC-F2006-03 | 통합 | `FakeEmbeddings`로 질문과 글자가 많이 겹치는 청크 하나를 만듦 | 그 청크가 외부 근거 첫 번째 | 03 | 〃 |
| TC-F2006-04 | 단위 | 병합 함수에 같은 ID 2개 · 같은 본문 다른 ID 2개 입력 | 각각 1개만 남고 번호 연속 | 04 | `tests/unit/test_merge.py` |
| TC-F2006-05 | 통합 | 외부 청크 10개, `top_k` 2 → 4 | 외부 근거 2개 → 4개 | 05 | `tests/integration/test_retriever.py` |
| TC-F2006-06 | 통합 | 외부 청크 0개인 영화 | 근거 1개, `no_external` | 06 | 〃 |
| TC-F2006-07 | 통합 | 빈 `movie_meta` | `IndexEmptyError` | 07 | 〃 |
| TC-F2006-08 | 수동 | Q1을 `--top-k 2`와 `--top-k 6`으로 실행 | 근거 목록 차이 캡처, 설계문서에 기록 | 05 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.3-1 | Top-k 2 / 4 / 6 근거 목록 비교 | `docs/verification/screenshots/V4.3-1_topk.png` |

## 8. 범위 밖

- MMR(SPEC-F2014). PDF 근거 결합(SPEC-F2016). 답변 생성(SPEC-F2007).
