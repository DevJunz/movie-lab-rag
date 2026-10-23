# SPEC-F2011 조건 기반 영화 탐색

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2011** 조건 기반 항목 탐색 (서비스 · 필수) |
| 구분 | MVP |
| 상태 | In Progress |
| 담당 모듈 | `movielab/services/explore.py`, `movielab/prompts.py`(E1, E2), `movielab/data/domain_movie.py`(`explore_filter_spec` · `explore_where`), `movielab/ui/pages/explore.py` |
| 선행 SPEC | SPEC-F2002, SPEC-F2009 |
| 관련 ISSUE | #16 |

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
| 4. 조건 선별 (E2) | 후보를 `- id=… | DomainProfile.item_card(항목, collect.card_overview_chars)` 줄로 보여 주고 조건에 맞는 영화만 `[{movie_id, reason}]`으로 받는다. 줄에 순번을 붙이지 않는다 — 실제 모델이 순번을 `movie_id`로 돌려준 일이 있어(§7 관찰) `id=` 값만 쓰게 한다 |
| 5. 검증 | 후보에 없는 `movie_id`는 버린다(목록 밖 영화 생성 방지). 2의 필터(`where`)를 후보 메타데이터에 다시 적용한다 — `$and` · `$gte` · `$lte` · `$eq`를 해석하는 도메인 무관 검사기(`services/explore.matches_where`). 같은 영화는 한 번만. 최대 `explore.max_results`(10)편 |
| 6. 표시 | 카드: 제목 (연도) · 요약 줄(`DomainProfile.item_caption`, F2009) · 선정 이유 · 메타 링크 · `이 영화로 질문하기` 버튼 |

- 후보가 0이거나 E2가 아무것도 고르지 않으면 `조건에 맞는 영화를 찾지 못했습니다.` 안내(`EXPLORE_EMPTY`).
- E1 · E2 응답이 JSON이 아니거나 형식이 틀리면: E1은 `{semantic_query: 조건 원문}`(필터 없음), E2는 선별 결과 없음으로 처리하고 로그만 남긴다.
- 진행 상태(F2012 방식): `explore_parse`(조건을 해석하는 중…) → `explore_search`(후보를 찾는 중…) → `explore_select`(조건에 맞는 영화를 고르는 중…).
- 메타 색인이 비면 탐색 입력을 비활성화한다(F2012 `INDEX_EMPTY`와 같은 조건).
- 화면은 `ui/pages/explore.py`의 `page_explore`를 `streamlit_app.PAGES`에 `조건 탐색`으로 등록한다.
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
- id=496243 | 기생충 (2019) / 장르: 코미디, 스릴러, 드라마 / 감독: 봉준호 / 줄거리(앞부분): …
…
출력은 JSON 배열 하나만: [{"movie_id": "후보 줄의 id= 뒤 값", "reason": "후보 정보에 근거한 한 문장"}]
```

### 3.3 카드 → 대화 연결

`이 영화로 질문하기` 클릭(버튼의 `on_click` 콜백) → `session_state["movie_id"] = movie_id`(사이드바 선택 상자의 키, F2009),
`session_state["page"] = "질문하기"`(메뉴 키) → 다음 실행에서 사이드바 선택과 메뉴가 바뀌고 그 영화의 대화 기록(F2009)이 보인다.
위젯 값은 위젯을 그리기 전(콜백)에 바꿔야 하므로 콜백으로 처리한다. 탐색 결과는 `session_state["explore_result"]`에 두어 다른 버튼을 눌러도 카드가 남는다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-11 | 후보 20편, 최대 10편 표시 (`settings.explore`) |

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
| TC-F2011-08 | 단위 | `matches_where`: `$and` · `$gte` · `$lte` · `$eq`, 필드 없음, `None` 조건 · `MOVIE_PROFILE.explore_where` 변환 | 기대한 참/거짓, `{year_min:1990, year_max:1999, korean_only:true}` → 세 조건의 `$and` | 03 | `tests/unit/test_explore.py` |
| TC-F2011-09 | 단위 | E1 · E2 프롬프트 | 머리표 `[작업: 조건 해석]` · `[작업: 조건 선별]`, 조건 · 후보 줄 · 필드 설명 포함 | 01, 02 | `tests/unit/test_prompts.py` |
| TC-F2011-10 | 통합 | `AppTest`: 빈 메타 색인 / 결과 없음 | 입력 비활성 / `EXPLORE_EMPTY` 안내 | 05 | `tests/integration/test_ui_explore.py` |
| TC-F2011-07 | 수동 | "우주를 배경으로 한 가족 영화" | 카드 결과와 조건 일치 여부를 사람이 확인해 기록 | 02 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.4-2 | 실제 색인 · GMS로 조건 2개("1990년대 한국 스릴러", "우주를 배경으로 한 가족 영화")의 해석 · 후보 수 · 결과 카드와 영화별 조건 일치표 (화면 캡처는 수동 단계) | `docs/verification/evidence/V4.4-2_explore.txt` |

## 8. 범위 밖

- 장르 · 감독 조건의 코드 강제 필터(장르명 표기 흔들림 때문에 LLM 선별에 맡긴다). 정렬 옵션.
