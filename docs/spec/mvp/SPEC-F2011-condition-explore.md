# SPEC-F2011 조건 기반 영화 탐색

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2011** 조건 기반 항목 탐색 (서비스 · 필수) |
| 구분 | MVP |
| 상태 | Draft |
| 담당 모듈 | `movielab/services/explore.py`, `movielab/prompts.py`(E1, E2), `movielab/ui/streamlit_app.py` |
| 선행 SPEC | SPEC-F2002, SPEC-F2009 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 사용자의 자연어 조건으로 항목을 검색하여 맞는 항목만 제시한다.

명세서 3장 세부 조건:
- ◆ 사용자는 원하는 항목의 조건을 자연어로 입력할 수 있어야 한다.
- ◆ 검색된 후보 중 조건에 맞는 항목만 선별하여 제시해야 한다.
- ◆ 제시된 항목을 선택하면 해당 항목에 대한 질문을 이어갈 수 있어야 한다.

## 2. 도메인 표현 (Movie Lab)

"1990년대 한국 스릴러", "우주를 배경으로 한 가족 영화"처럼 조건을 입력하면, 메타데이터 색인에서 후보를 찾고 LLM이 조건에 맞는 영화만 골라 카드로 보여 준다.
카드를 누르면 그 영화가 선택되고 질문하기 화면으로 넘어간다.

## 3. 상세 명세

### 3.1 절차 (`ExploreService.search(condition) -> ExploreResult`)

| 단계 | 내용 |
|---|---|
| 1. 조건 해석 (E1) | 자연어 조건 → `{semantic_query, year_min, year_max, korean_only}`. 파싱 실패 시 `{semantic_query: 조건 원문, 나머지 null}` |
| 2. 메타데이터 필터 | 해석한 값 중 **확실히 구조화된 조건**(연도 범위, 한국 영화 여부)은 Chroma `where`로 강제한다: `year >= year_min`, `year <= year_max`, `original_language == "ko"`. 변환은 `DomainProfile.explore_where(parsed)`가 맡는다(영화 필드 이름은 `data/`에만 둔다, NF2005) |
| 3. 의미 검색 | `movie_meta`에서 `semantic_query`로 `explore.candidates`(20)편 검색 (2의 필터 적용) |
| 4. 조건 선별 (E2) | 후보의 색인 텍스트(번호 · `movie_id` · 줄거리 앞 200자)를 보여 주고 조건에 맞는 영화만 `[{movie_id, reason}]`으로 받는다 |
| 5. 검증 | 후보에 없는 `movie_id`는 버린다(목록 밖 영화 생성 방지). 2의 필터를 다시 확인한다. 최대 `explore.max_results`(10)편 |
| 6. 표시 | 카드: 제목 (연도) · 장르 · 감독 · 선정 이유 · `이 영화로 질문하기` 버튼 |

- 후보가 0이거나 E2가 아무것도 고르지 않으면 `조건에 맞는 영화를 찾지 못했습니다.` 안내.
- 선정 이유는 후보 메타데이터에 근거해야 한다. 카드에는 출처 `영화 메타데이터 · TMDB ↗` 링크를 둔다(근거 제시).

### 3.2 프롬프트

```text
[작업: 조건 해석]
너는 {expert_role}이다. 사용자의 {item_label} 탐색 조건을 해석하라.
출력은 JSON 객체 하나만:
{"semantic_query": "의미 검색에 쓸 문장", <explore_filter_spec의 필드들>}
{explore_filter_spec의 규칙 설명}
조건: {condition}
```

영화 프로필의 `explore_filter_spec`:

```text
필드: "year_min": 정수|null, "year_max": 정수|null, "korean_only": true|false|null
- 연도 · 연대가 명시된 경우에만 year_min/year_max를 채운다. ("90년대" → 1990, 1999)
- "한국 영화", "국내 영화"가 명시된 경우에만 korean_only=true.
```

```text
[작업: 조건 선별]
너는 {expert_role}이다. 아래 후보 중 조건에 **모두** 맞는 영화만 고른다. 애매하면 고르지 않는다.
조건: {condition}
후보 (각 줄은 DomainProfile.item_card):
[0] id=496243 | 기생충 (2019) / 장르: 코미디, 스릴러, 드라마 / 감독: 봉준호 / 줄거리(앞부분): …
…
출력은 JSON 배열 하나만: [{"movie_id": "…", "reason": "후보 정보에 근거한 한 문장"}]
```

### 3.3 카드 → 대화 연결

`이 영화로 질문하기` 클릭 → `session_state["selected_movie_id"] = movie_id`, `session_state["page"] = "질문하기"` → `st.rerun()`.
사이드바 선택 상자도 같은 값으로 바뀌고, 그 영화의 대화 기록(F2009)이 보인다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-11 | 후보 20편, 최대 10편 표시 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2011-01 | 자연어 조건을 입력할 수 있고, 결과는 카드 목록으로 나온다 | — |
| AC-F2011-02 | 결과는 의미 검색 후보 안에서만 나오고, LLM이 고른 영화만 나온다 | V4.4-2 |
| AC-F2011-03 | 연도 범위 · 한국 영화 조건이 해석되면 그 조건에 맞지 않는 영화는 결과에 절대 나오지 않는다 (코드로 강제) | V4.4-2 |
| AC-F2011-04 | 카드를 누르면 그 영화가 선택되고 질문하기 화면으로 바뀐다 | — |
| AC-F2011-05 | 맞는 영화가 없으면 안내가 나온다 | — |
| AC-F2011-06 | E1 · E2 출력이 깨져도 예외 없이 처리된다 | — |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2011-01 | 단위 | E2가 후보에 없는 `movie_id` 반환 | 결과에서 제외 | 02 | `tests/unit/test_explore.py` |
| TC-F2011-02 | 통합 | 합성 12편 색인, E1 `{year_min:1990, year_max:1999, korean_only:true}`, E2가 2000년 영화 · 해외 영화까지 고름 | 결과에 1990년대 한국 영화만 | 03 | `tests/integration/test_explore.py` |
| TC-F2011-03 | 통합 | E1 · E2 깨진 응답 | 예외 없음, 안내 또는 필터 없는 검색 | 06 | 〃 |
| TC-F2011-04 | 통합 | E2 `[]` | `조건에 맞는 영화를 찾지 못했습니다.` | 05 | 〃 |
| TC-F2011-05 | 통합 | `AppTest`: 조건 입력 → 카드 버튼 클릭 | `selected_movie_id` 변경, 페이지 `질문하기` | 01, 04 | `tests/integration/test_ui_explore.py` |
| TC-F2011-06 | live | "1990년대 한국 스릴러" | 결과 모두 `year ∈ [1990,1999]`, `original_language == "ko"` | 02, 03 | `tests/live/test_live_explore.py` |
| TC-F2011-07 | 수동 | "우주를 배경으로 한 가족 영화" | 카드 결과와 조건 일치 여부를 사람이 확인해 기록 | 02 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.4-2 | 조건 2개의 결과 화면 + 각 영화 조건 일치표 | `docs/verification/screenshots/V4.4-2_explore_*.png` |

## 8. 범위 밖

- 장르 · 감독 조건의 코드 강제 필터(장르명 표기 흔들림 때문에 LLM 선별에 맡긴다). 정렬 옵션.
