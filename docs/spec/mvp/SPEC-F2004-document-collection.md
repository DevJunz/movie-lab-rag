# SPEC-F2004 위키백과 문서 수집 (프롬프트 2)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2004** 외부 문서 수집(프롬프트2) (수집 · 필수) |
| 구분 | MVP |
| 상태 | Draft |
| 담당 모듈 | `movielab/collect/selector.py`, `movielab/collect/collector.py`, `movielab/data/wiki_api.py`, `movielab/data/wiki_bundle.py`, `movielab/data/raw_store.py`, `movielab/data/domain_movie.py` |
| 선행 SPEC | SPEC-F2003, SPEC-NF2006 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 외부 문서 출처에서 검색하고, 선별 프롬프트로 후보 중 색인할 문서를 선별하여 본문과 원문 출처를 수집한다.

명세서 3장 세부 조건:
- ◆ 외부 문서 출처에서 검색하여 후보 문서를 모아야 한다.
- ◆ 후보 선별 프롬프트(프롬프트 2)로 관련성이 높은 문서만 선별하여 색인해야 한다.
- ◆ 선택한 항목 자체를 다룬 문서는 선별 · 길이 등 어떤 제외 규칙보다 우선하여 항상 색인해야 한다.
- ◆ 선별된 문서의 본문과 원문 출처(URL 또는 파일명과 쪽)를 수집해야 한다.
- ◆ 이미 수집한 검색어는 다시 수집하지 않아야 한다. → 상세 규칙은 SPEC-NF2002
- ◆ 외부 문서 호출이 제한되는 환경에서는 제공된 문서 묶음을 읽어 수집 단계를 대신할 수 있다.

## 2. 도메인 표현 (Movie Lab)

검색어마다 한국어 위키백과에서 후보(제목 · 요약)를 모은 뒤, 프롬프트 2가 질문에 도움이 될 문서만 고른다.
선택한 영화 자체를 다룬 문서는 항상 수집한다. 위키백과 호출이 막히면 `movielab_wiki/` 묶음에서 같은 절차(검색 → 선별 → 수집)를 수행한다.
**프롬프트 1 · 2와 선별 코드는 묶음을 쓸 때도 그대로 실행한다.**

## 3. 상세 명세

### 3.1 문서 소스 인터페이스

`collect`는 구체 구현을 모른다. `container.py`가 소스를 골라 주입한다.

```python
class DocumentSource(Protocol):                      # movielab/core/types.py
    kind: str                                        # "api" | "bundle"
    def search(self, query: str, limit: int) -> list[Candidate]: ...
    def resolve_titles(self, titles: list[str]) -> list[Candidate]: ...   # 제목 직접 조회 (넘겨주기 따라감)
    def fetch(self, page_id: str) -> SourceDocument | None: ...           # 본문 + 원문 URL
```

| 구현 | 위치 | 방식 |
|---|---|---|
| `WikiApiSource` | `data/wiki_api.py` | MediaWiki API. 호출 규칙은 SPEC-NF2006 |
| `WikiBundleSource` | `data/wiki_bundle.py` | `movielab_wiki/wikipedia/*.json`을 읽어 메모리 색인(제목 · 본문). 외부 호출 없음 |

**WikiApiSource 요청** (모두 `format=json`, `formatversion=2`, `maxlag=5`):

| 기능 | 파라미터 |
|---|---|
| 검색 | `action=query&list=search&srsearch={q}&srlimit={search_limit}&srnamespace=0&srprop=snippet\|size` |
| 제목 조회 | `action=query&titles={t1}\|{t2}\|{t3}&redirects=1&prop=info\|pageprops&ppprop=disambiguation&inprop=url` |
| 본문 | `action=query&pageids={id}&prop=extracts\|info&explaintext=1&inprop=url` |

- 검색 요약(snippet)의 HTML 태그(`<span class="searchmatch">` 등)는 지우고 HTML 엔티티를 푼다.
- 본문은 한 번에 문서 1개만 요청한다(TextExtracts는 전문 추출 시 1건 제한).

**WikiBundleSource 규칙**:
- `search(q)`: 묶음 전체에서 정규화한 `q`가 제목에 들어 있거나 본문 앞 2,000자에 나오는 문서를 찾는다. 점수는 제목 일치 > 제목 포함 > 본문 등장 횟수 순이고, **현재 영화의 문서에 가산점**을 준다. 같은 `page_id`는 하나로 합친다. snippet은 `q`가 처음 나온 곳 앞뒤 150자다.
- `resolve_titles`: 제목이 정확히 같은 문서.
- `fetch`: 저장된 본문과 URL을 돌려준다. `movie_id` · `related_movie` · `search_query`는 **현재 수집 맥락의 값으로 바꿔** 반환한다.

### 3.2 소스 선택 (`collect.source`)

| 값 | 동작 |
|---|---|
| `api` | 위키백과 API만 쓴다. 막히면 `ExternalSourceUnavailableError` |
| `bundle` | 제공 묶음만 쓴다 |
| `auto` (기본, A-17) | `WIKI_CONTACT`가 없으면 처음부터 묶음을 쓴다. API가 재시도 후에도 실패하면(네트워크 오류, 403, 반복된 429/503) **그 수집의 남은 단계를 묶음으로 전환**한다. 두 경우 모두 `notices`에 `SOURCE_FALLBACK`을 남기고 화면에 안내한다(F2012) |

### 3.3 수집 절차 (`Collector.collect(item, question, on_progress)`)

| 단계 | 진행 상태 키 | 내용 |
|---|---|---|
| 1 | `extract_queries` | SPEC-F2003으로 `QueryPlan`을 얻는다 (질문 캐시 적중 시 생략 — NF2002) |
| 2 | `resolve_item_doc` | §3.4로 항목 자체 문서를 찾는다 |
| 3 | `search` | 캐시에 없는 검색어만 검색한다(NF2002). 후보를 `page_id`로 합치고, 이 영화로 이미 수집한 `page_id`는 뺀다 |
| 4 | `filter` | §3.5 제외 규칙 적용 (항목 자체 문서는 면제) |
| 5 | `select` | §3.6 프롬프트 2로 선별 |
| 6 | `fetch` | 항목 자체 문서 → 선별 문서 순으로 본문 수집. 본문 길이 규칙 재적용(항목 자체 문서 면제). `data/raw/wiki/{movie_id}_{안전한 제목}.json`에 저장 |
| 7 | `index` | SPEC-F2005로 청킹 · 색인 |
| 8 | `done` | 매니페스트 갱신(NF2002), `CollectReport` 반환 |

- `on_progress(stage: str, info: dict)` 콜백은 UI에 독립적이다. UI는 이를 진행 상태 영역에 표시한다(F2012).
- `CollectReport`에는 **색인된 문서와 버려진 문서를 사유와 함께** 남긴다. 사유: `p2_not_selected`, `too_short`, `disambiguation`, `already_collected`, `fetch_failed` (V4.2-2).
- 수집 실패(본문 조회 실패 등)는 해당 문서만 건너뛰고 계속한다. 문서가 하나도 없어도 예외로 끝내지 않는다 → 답변은 메타 근거만으로 진행(F2006, F2012의 "검색 결과 없음" 안내).

### 3.4 항목 자체 문서 판별 (`DomainProfile.pick_item_doc`, `data/domain_movie.py`)

1. `resolve_titles(item_queries)` — `「{title} ({year}년 영화)」`, `「{title} (영화)」`, `「{title}」` (SPEC-F2003 §3.2).
2. 동음이의 문서는 제외한다.
3. 앞 순서부터 존재하는 첫 문서를 고른다. **단, `「{title}」`(괄호 없는 제목)은** 영화 전용 표제(1·2번)가 하나도 없고,
   본문 앞 300자에 `영화`가 있으며 `연도` 또는 `감독 이름`이 있을 때만 고른다.
   - 예) 「미녀와 야수」(2017) → 「미녀와 야수 (2017년 영화)」 선택. 괄호 없는 「미녀와 야수」(동화)는 고르지 않는다.
   - 예) 「인터스텔라」 → 1·2번이 없고 본문이 "…2014년 … 영화이다"이므로 「인터스텔라」 선택.
4. 고른 문서는 `is_item_doc=True`로 표시하고 **P2 · 개수 상한 · 길이 규칙과 상관없이 항상 수집 · 색인**한다. 상한(`max_selected_docs`)에도 세지 않는다.
5. 찾지 못하면 `notices`에 `ITEM_DOC_NOT_FOUND`를 남기고 계속한다.

### 3.5 제외 규칙 (항목 자체 문서 면제)

| 규칙 | 기준 | 사유 코드 |
|---|---|---|
| 동음이의 문서 | `pageprops.disambiguation` 또는 제목이 `(동음이의)`로 끝남 | `disambiguation` |
| 너무 짧은 문서 | 본문 `min_doc_chars`(200)자 미만 | `too_short` |
| 이미 수집 | 이 영화로 이미 수집한 `page_id` | `already_collected` |

### 3.6 프롬프트 P2 (후보 선별)

```text
[작업: 후보 선별]
너는 자료 조사원이다. {item_label} '{제목} ({연도})'에 대한 질문에 답하는 데 도움이 될 문서를 고른다.
질문: {question}

후보 (번호. 제목: 요약):
0. 블랙홀: 블랙홀은 중력이 매우 강해 빛조차 빠져나올 수 없는 천체이다…
1. 블랙홀 (음반): …

규칙:
- 질문에 답하는 데 직접 도움이 되는 문서만 고른다. 최대 {max_selected_docs}개.
- 제목이 같아도 다른 대상(음반, 동명 인물 등)을 다룬 문서는 고르지 않는다.
- 출력은 고른 번호의 JSON 정수 배열 하나만. 고를 것이 없으면 [].
```

- 본문을 받기 **전에** 제목과 요약만 보여 준다(외부 호출 수 절약, 명세서 2.4).
- 출력 검증: 정수가 아니거나 범위 밖인 번호는 버리고, 중복을 없애고, `max_selected_docs`개까지 자른다. 파싱 실패 시 빈 배열 → 항목 자체 문서만 수집.
- 후보가 0개면 P2를 부르지 않는다.

### 3.7 인터페이스

```python
class CandidateSelector:
    def __init__(self, llm, profile, settings): ...
    def select(self, item, question, candidates: list[Candidate]) -> SelectionResult: ...  # selected, rejected(사유)

class Collector:
    def __init__(self, source_factory, extractor, selector, manifest, raw_store, doc_indexer, profile, settings): ...
    def collect(self, item: ItemRecord, question: str, on_progress=None) -> CollectReport: ...
```

```text
python -m scripts.collect --movie-id 157336 --question "<질문>" [--source api|bundle|auto] [--dry-run]
  → 검색어, 후보, 선별/버림(사유), 색인된 문서 제목, 사용한 소스를 출력. --dry-run은 색인 전까지만
```

## 4. 가정

| ID | 내용 |
|---|---|
| A-05 | 검색어당 후보 5개, 선별 최대 5문서 (항목 자체 문서 별도) |
| A-06 | 200자 미만 · 동음이의 문서 제외 (항목 자체 문서 면제) |
| A-07 | 질문할 때 수집 |
| A-17 | 소스 기본값 `auto` |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2004-01 | 검색어마다 소스에서 후보를 모으고, 같은 문서는 하나로 합친다 | V4.2-2 |
| AC-F2004-02 | P2에는 후보의 제목과 요약만 들어가고 본문은 들어가지 않는다. P2가 고른 문서만(＋항목 자체 문서) 본문을 수집한다 | V4.2-2 |
| AC-F2004-03 | 항목 자체 문서는 P2가 고르지 않아도, 짧아도, 상한을 넘어도 수집 · 색인된다 | V4.2-4 |
| AC-F2004-04 | 동명 작품이 있으면 `「제목 (연도년 영화)」`를 고르고 괄호 없는 동명 문서(동화 등)를 항목 자체 문서로 고르지 않는다 | V4.2-4 |
| AC-F2004-05 | 수집 결과에 문서 본문과 원문 URL이 있고, `data/raw/wiki/`에 4.2 형식으로 저장된다 | — |
| AC-F2004-06 | `CollectReport`에 색인된 문서와 버려진 문서가 사유와 함께 남는다 | V4.2-2 |
| AC-F2004-07 | P2 출력이 깨지거나 범위 밖 번호를 포함해도 예외 없이 처리된다 | — |
| AC-F2004-08 | `bundle` 소스로도 같은 절차(P1 → 검색 → P2 → 수집 → 색인)가 실행된다 | — |
| AC-F2004-09 | `auto`에서 API 실패 시 묶음으로 전환하고 `SOURCE_FALLBACK` 안내를 남긴다 | (F2012) |
| AC-F2004-10 | 진행 상태 콜백이 §3.3 순서로 호출된다 | V4.4-4 |
| AC-F2004-11 | 이미 수집한 검색어 · 문서는 다시 수집하지 않는다 (SPEC-NF2002의 AC로 검증) | V4.2-3 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2004-01 | 단위 | 가짜 소스: 검색어 2개가 같은 문서를 돌려줌 | 후보 1개로 합쳐짐 | 01 | `tests/unit/test_collector.py` |
| TC-F2004-02 | 단위 | `FakeChatModel`이 받은 P2 프롬프트 검사 | 제목 · 요약 포함, 본문 문자열 미포함, JSON 정수 배열 지시 | 02 | `tests/unit/test_selector.py` |
| TC-F2004-03 | 단위 | P2가 `[1]`만 고름 (후보 3개) | `fetch`는 항목 자체 문서 + 1번만 호출, 나머지는 `p2_not_selected` | 02, 06 | `tests/unit/test_collector.py` |
| TC-F2004-04 | 단위 | P2가 `[]`, 항목 자체 문서 본문 150자, 상한 0 | 항목 자체 문서는 수집 · 색인됨 | 03 | 〃 |
| TC-F2004-05 | 단위 | 합성 「미녀와 야수」(동화) + 「미녀와 야수 (2017년 영화)」 | 영화 문서가 항목 자체 문서로 선택 | 04 | `tests/unit/test_domain_movie.py` |
| TC-F2004-06 | 단위 | 영화 전용 표제 없음 + 괄호 없는 제목 문서 앞 300자에 `영화`·연도 있음 / 없음 | 있음: 선택 / 없음: 미선택, `ITEM_DOC_NOT_FOUND` | 04 | 〃 |
| TC-F2004-07 | 단위 | P2 응답 `["1", 7, -1, 1, "x"]` (후보 3개) | 유효 번호만 반영, 예외 없음 | 07 | `tests/unit/test_selector.py` |
| TC-F2004-08 | 단위 | 동음이의 · 199자 문서 후보 | 각각 `disambiguation` · `too_short`로 버려짐 | 06 | `tests/unit/test_collector.py` |
| TC-F2004-09 | 단위 | `WikiApiSource` + `FakeHttpSession`: 검색 · 제목 조회 · 본문 응답 | snippet 태그 제거, `page_id` 문자열, URL 수집 | 05 | `tests/unit/test_wiki_api.py` |
| TC-F2004-10 | 통합 | `WikiBundleSource`(합성 묶음) + 가짜 LLM + 임시 Chroma로 전체 수집 | P1 · P2가 호출되고, 선택 문서가 `wiki_docs`에 색인되고 raw 파일 저장 | 05, 08 | `tests/integration/test_collect_bundle.py` |
| TC-F2004-11 | 통합 | `auto` + API가 계속 503 | 묶음으로 전환, `SOURCE_FALLBACK`, 수집 성공 | 09 | `tests/integration/test_collect_fallback.py` |
| TC-F2004-12 | 통합 | `auto` + `WIKI_CONTACT` 없음 | API 호출 0회, 묶음 사용, `SOURCE_FALLBACK` | 09 | 〃 |
| TC-F2004-13 | 단위 | 진행 상태 콜백 기록 | `extract_queries → resolve_item_doc → search → filter → select → fetch → index → done` | 10 | `tests/unit/test_collector.py` |
| TC-F2004-14 | live | 실제 위키백과 + GMS로 Q1 수집 | 「인터스텔라」가 항목 자체 문서로 색인, 원문 URL이 `https://ko.wikipedia.org/wiki/`로 시작 | 03, 05 | `tests/live/test_live_collect.py` |
| TC-F2004-15 | 수동 | Q1 수집 후 화면의 "수집 상세" 또는 스크립트 출력 | 색인된 문서와 버려진 문서(사유)를 구분해 보여 줌 | 06 | 스크린샷 |
| TC-F2004-16 | 통합 | 같은 질문 2회 수집 (TC-NF2002-01과 같은 테스트) | 2회째 소스 검색 · 본문 요청 0회 | 11 | `tests/integration/test_cache_path.py` |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-2 | Q1 수집 결과의 색인 / 버림 목록 캡처 | `docs/verification/screenshots/V4.2-2_selection.png` |
| V4.2-4 | 항목 자체 문서(「인터스텔라」, 「미녀와 야수 (2017년 영화)」)가 색인된 결과 캡처 | `docs/verification/screenshots/V4.2-4_item_doc.png` |

## 8. 범위 밖

- 호출 간격 · 재시도 · User-Agent(SPEC-NF2006). 캐시 규칙(SPEC-NF2002). 청킹(SPEC-F2005). PDF 소스(SPEC-F2016).
