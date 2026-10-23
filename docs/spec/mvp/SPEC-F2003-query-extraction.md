# SPEC-F2003 검색어 추출 (프롬프트 1)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2003** 검색어 추출(프롬프트1) (프롬프트 · 필수) |
| 구분 | MVP |
| 상태 | Done |
| 담당 모듈 | `movielab/collect/query_extractor.py`, `movielab/prompts.py`(P1), `movielab/core/jsonparse.py`, `movielab/data/domain_movie.py` |
| 선행 SPEC | SPEC-F2001 |
| 관련 ISSUE | #6 |

## 1. 요구사항 원문

> 도메인 전문가 역할 프롬프트로 항목과 질문에서 외부 문서 검색어를 추출한다.

명세서 3장 세부 조건:
- ◆ 도메인 전문가 역할을 부여한 프롬프트(프롬프트 1)로 외부 문서 검색어를 추출해야 한다.
- ◆ 선택한 항목 자체를 다룬 문서는 항상 검색 대상에 포함해야 한다.
- ◆ 추출 결과는 파싱 가능한 형식으로 받아야 한다.

## 2. 도메인 표현 (Movie Lab)

"영화 큐레이터" 역할로, 선택한 영화와 질문에서 한국어 위키백과 검색어를 JSON 배열로 뽑는다.
선택한 영화 자체의 문서를 찾는 검색어는 LLM 결과와 상관없이 항상 넣는다.

## 3. 상세 명세

### 3.1 프롬프트 P1

```text
[작업: 검색어 추출]
너는 {expert_role}이다.            ← DomainProfile.expert_role = "영화 큐레이터"
아래 {item_label}과 질문에 답하려면 한국어 위키백과에서 어떤 문서를 찾아봐야 하는지 정하라.

{item_label}: {item_card}          ← DomainProfile.item_card(item)
질문: {question}

규칙:
- 위키백과 문서 제목이 될 만한 짧은 명사구로 {min_queries}~{max_queries}개를 고른다.
- 질문에 나온 인물 · 사건 · 개념 · 장소를 우선한다.
- 출력은 JSON 문자열 배열 하나만. 설명을 붙이지 않는다.
예: ["블랙홀", "웜홀", "일반 상대성 이론"]
```

`item_card`(영화, `data/domain_movie.py`): 줄거리는 `ItemRecord.index_text`의 `줄거리:` 줄에서 읽는다(메타데이터에 줄거리를 중복 저장하지 않기 위해). `인터스텔라 (2014) / 원제: Interstellar / 감독: 크리스토퍼 놀란 / 장르: 모험, 드라마, SF / 줄거리(앞부분): 세계 각국의 정부와 …(300자)`.
영화 필드 이름을 프롬프트 템플릿에 직접 쓰지 않기 위해 프로필이 만든다(NF2005).

### 3.2 항목 자체 문서 검색어 (항상 포함)

`DomainProfile.item_doc_queries(movie)`가 만든다(영화 도메인 규칙이라 `data/domain_movie.py`에 둔다).

| 순서 | 검색어 | 용도 |
|---|---|---|
| 1 | `{title} ({year}년 영화)` | 제목 직접 조회 — 동명 작품이 있을 때의 위키백과 표제 형식 |
| 2 | `{title} (영화)` | 제목 직접 조회 |
| 3 | `{title}` | 제목 직접 조회 + 검색 |

이 검색어로 실제 문서를 찾고 고르는 규칙은 SPEC-F2004 §3.4에 있다.

### 3.3 후처리

1. `core.jsonparse.parse_json_array(text)`로 읽는다: 코드 펜스 제거 → 첫 `[` ~ 마지막 `]` → `json.loads`.
2. 문자열이 아닌 값 · 빈 문자열을 버리고, 앞뒤 공백을 지우고, 정규화 키(소문자 · 공백 1칸) 기준으로 중복을 없앤다.
3. 항목 자체 검색어와 겹치는 것은 버린다. `max_queries`개를 넘으면 앞에서부터 자른다.
4. 파싱에 실패하거나 결과가 0개면 **항목 자체 검색어만** 쓰고 `CollectReport.notices`에 `P1_FALLBACK`을 남긴다(사용자에게는 표시하지 않음).
5. LLM 호출 자체가 실패하면 4와 같이 처리하고 원인은 로그에만 남긴다.

### 3.4 인터페이스

```python
# movielab/collect/query_extractor.py
@dataclass
class QueryPlan:
    item_queries: list[str]   # 3.2, 항상 포함
    llm_queries: list[str]    # P1 결과(후처리 후)
    fallback: bool
    @property
    def all(self) -> list[str]: ...   # item_queries + llm_queries (중복 없음, 순서 유지)

class QueryExtractor:
    def __init__(self, llm, profile: DomainProfile, settings): ...
    def extract(self, item: ItemRecord, question: str) -> QueryPlan: ...
```

- `QueryPlan`은 `CollectReport.queries`로 화면(진행 상태 · 수집 상세)과 `scripts.collect` 출력에 나온다 (V4.2-1).
- 같은 영화 · 같은 질문의 `QueryPlan`은 매니페스트 `questions`에 저장해 재사용한다(SPEC-NF2002). 이때는 P1을 부르지 않는다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-05 | 검색어 3~5개 (`collect.min_queries`, `collect.max_queries`) |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2003-01 | P1 프롬프트에 도메인 전문가 역할(`영화 큐레이터`), 영화 정보, 질문, JSON 배열 출력 지시가 들어간다 | V4.2-1 |
| AC-F2003-02 | 항목 자체 검색어 3개가 LLM 결과와 상관없이 항상 `QueryPlan.all` 앞에 있다 | V4.2-4 |
| AC-F2003-03 | LLM이 설명 문장 · 코드 펜스를 섞어도 배열을 읽는다 | — |
| AC-F2003-04 | 파싱 실패 · LLM 오류 시 예외 없이 항목 자체 검색어만 반환하고 `fallback=True` | — |
| AC-F2003-05 | 중복 · 빈 값 · 비문자열을 제거하고 `max_queries`를 넘지 않는다 | — |
| AC-F2003-06 | 하나의 질문에 대해 뽑힌 검색어 목록을 스크립트 출력과 화면에서 확인할 수 있다 | V4.2-1 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2003-01 | 단위 | `FakeChatModel`이 받은 P1 프롬프트 검사 | `[작업: 검색어 추출]`, `영화 큐레이터`, 제목 · 질문, `JSON` 포함 | 01 | `tests/unit/test_query_extractor.py` |
| TC-F2003-02 | 단위 | LLM 응답 `["웜홀","블랙홀"]` | `all == [항목 3개] + ["웜홀","블랙홀"]` | 02 | 〃 |
| TC-F2003-03 | 단위 | 응답 ```` ```json\n["웜홀"]\n``` 참고하세요 ```` | `llm_queries == ["웜홀"]` | 03 | 〃 |
| TC-F2003-04 | 단위 | 응답 `"검색어는 웜홀입니다"` | `llm_queries == []`, `fallback`, 항목 검색어 3개 유지 | 04 | 〃 |
| TC-F2003-05 | 단위 | LLM이 예외를 던짐 | 예외 전파 없음, `fallback` | 04 | 〃 |
| TC-F2003-06 | 단위 | 응답 `["웜홀"," 웜홀 ","",3,"인터스텔라","a","b","c","d","e"]` | 중복 · 빈 값 · 숫자 · 항목 제목 제거, 최대 5개 | 05 | 〃 |
| TC-F2003-07 | 단위 | 동명 영화(합성 「미녀와 야수」 1991/2017) | 항목 검색어에 `(1991년 영화)` / `(2017년 영화)`가 각각 들어감 | 02 | `tests/unit/test_domain_movie.py` |
| TC-F2003-08 | 단위 | `parse_json_array` 경계값 (빈 문자열, `[]`, 중첩 배열, 깨진 JSON) | 정의된 기본값 반환 | 03, 04 | `tests/unit/test_jsonparse.py` |
| TC-F2003-09 | live | 실제 GMS로 Q1 검색어 추출 | 파싱 성공, 1~5개, `fallback == False` | 01, 03 | `tests/live/test_live_prompts.py` |
| TC-F2003-10 | 수동 | `python -m scripts.collect --movie-id 157336 --question "<Q1>" --dry-run` | 검색어 목록 출력 | 06 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-1 | Q1의 검색어 목록 (실제 GMS 결과 저장, 화면의 수집 상세 캡처는 F2012 이후) | `docs/verification/evidence/V4.2-1_queries.txt` |

## 8. 범위 밖

- 실제 검색 · 선별 · 수집(SPEC-F2004). 캐시 재사용 규칙(SPEC-NF2002).
