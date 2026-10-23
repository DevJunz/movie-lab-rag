# SPEC-NF2002 수집 캐시

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2002** 수집 캐시 (성능) |
| 구분 | MVP (비기능) |
| 상태 | Done |
| 담당 모듈 | `movielab/collect/manifest.py`, `movielab/collect/collector.py` |
| 선행 SPEC | SPEC-F2004 |
| 관련 ISSUE | #8 |

## 1. 요구사항 원문

> 이미 수집 · 색인한 검색어는 다시 수집하지 않아야 한다.

F2004 세부 조건 "◆ 이미 수집한 검색어는 다시 수집하지 않아야 한다."도 이 SPEC으로 만족시킨다.

## 2. 도메인 표현 (Movie Lab)

영화별로 이미 검색한 검색어, 수집한 문서, 처리한 질문을 `data/manifest.json`에 기록한다(제공 `wiki_manifest.json`과 호환되는 형식).
같은 질문을 다시 하면 검색어 추출부터 건너뛰고, 다른 질문이라도 이미 검색한 검색어는 다시 검색하지 않는다.

## 3. 상세 명세

### 3.1 매니페스트 형식

[01-architecture.md §4.3](../01-architecture.md#43-수집-매니페스트-datamanifestjson) 참조. 영화 ID 키 아래:
`keywords`(검색한 검색어), `titles`, `page_ids`(문자열), `questions`(정규화 질문 → 검색어 목록), `rejected_page_ids`(기록용), `chunks`, `collected_at`.

### 3.2 캐시 규칙

| 단계 | 캐시 확인 | 적중 시 |
|---|---|---|
| 질문 | `normalize(question) in questions[movie_id]` | P1 호출 생략, 저장된 검색어 사용. 그 검색어가 모두 `keywords`에 있으면 **수집 전체 생략** → 진행 상태 `cache_hit` |
| 검색어 | `normalize(q) in keywords[movie_id]` | 그 검색어의 소스 검색 생략 |
| 문서 | `page_id in page_ids[movie_id]` | 본문 수집 · 색인 생략 (`already_collected`) |
| 항목 자체 문서 | 매니페스트의 `item_doc_page_id`가 있음 | 제목 조회 생략, 그 문서를 이미 수집한 것으로 본다 |

- `normalize`: 앞뒤 공백 제거, 연속 공백 1칸, 소문자화, 유니코드 NFC.
- 문서는 **색인까지 마친 뒤에만**(청크 1개 이상) `page_ids`에 기록한다. 색인기가 없으면(`--dry-run` 등) 아무것도 기록하지 않는다.
- 검색어 · 질문은 **그 수집이 완전히 성공했을 때만** 기록한다: 검색이 설정한 소스로 끝났고, 고른 문서(항목 자체 문서 포함)에 `fetch_failed` · `index_failed`가 하나도 없을 때. 하나라도 실패하면 성공한 문서만 기록하고 검색어 · 질문은 기록하지 않아, 같은 질문을 다시 하면 실패한 문서를 다시 시도한다.
- **색인 확인**: 수집을 시작할 때 그 영화의 청크가 0개인데 매니페스트에 **색인했다고 기록된 문서(`page_ids`)**가 있으면(`data/chroma`를 지운 경우 등) 질문 캐시 적중 여부와 상관없이 그 영화의 매니페스트를 비우고 새로 수집한다.
  색인한 문서가 하나도 없던 영화(검색 결과에서 고른 문서가 없음)는 청크가 0개인 것이 정상이므로 캐시를 비우지 않는다.
- 캐시는 영화별이다. 영화 A에서 검색한 「크리스토퍼 놀란」은 영화 B에서 다시 검색될 수 있다(청크 ID가 영화별이기 때문, F2005).

### 3.3 저장 안전성

- 매니페스트는 여러 인스턴스 · 프로세스(앱과 `--reset-cache` 스크립트 등)가 함께 쓴다. **파일이 바뀌었으면(수정 시각) 읽기 · 쓰기 전에 다시 읽고**, 쓰기는 고유한 임시 파일 이름으로 한 뒤 바꿔 넣는다.
- 구조가 틀린 내용(최상위가 객체가 아님, 항목 값이 객체가 아님, 목록 필드가 목록이 아님)도 깨진 파일과 같게 처리한다(백업 후 새로 시작).
- 날짜(`collected_at`) · 백업 시각은 주입된 함수로 정한다. 백업 파일 이름은 겹치지 않게 만든다.

- 쓰기는 임시 파일에 쓴 뒤 `os.replace`로 바꾼다(중간에 끊겨도 깨진 JSON이 남지 않음).
- 파일이 없으면 빈 매니페스트로 시작한다. JSON이 깨져 있으면 `manifest.json.broken-<시각>`으로 옮겨 두고 빈 매니페스트로 시작하며 경고 로그를 남긴다.
- 캐시를 지우는 명령: `python -m scripts.collect --reset-cache [--movie-id ID]` (LLM · 키 없이 동작, `Services.manifest`).
- 매니페스트와 Chroma가 어긋나는 경우(사용자가 `data/chroma`만 지운 경우)를 위해 `scripts.collect --reset-cache [--movie-id]`로 캐시를 지울 수 있다.
  또한 질문 캐시 적중이지만 `wiki_docs`에 그 영화 청크가 0개면 캐시를 믿지 않고 다시 수집한다. 청크 유무는 `Collector`에 주입한 `has_chunks(item_id)`로 확인한다(색인기는 F2005에서 연결 — 주입되지 않으면 이 확인을 건너뛴다).
- 매니페스트 형식에 `item_doc_page_id`(항목 자체 문서의 page_id)를 더한다.
- 질문 캐시 적중으로 수집 전체를 생략하면 `CollectReport.notices`에 `CACHE_HIT`를 남기고 `source_used = "cache"`(01-architecture §4.4의 값 목록에 추가), 진행 상태 `cache_hit` → `done`만 보낸다.

### 3.4 인터페이스

```python
class Manifest:
    def __init__(self, path: Path): ...
    def cached_queries(self, movie_id, question) -> list[str] | None: ...
    def has_keyword(self, movie_id, query) -> bool: ...
    def has_page(self, movie_id, page_id) -> bool: ...
    def record_question(self, movie_id, question, queries) -> None: ...
    def record_keyword(self, movie_id, query) -> None: ...
    def record_page(self, movie_id, page_id, title, chunks, rejected=False) -> None: ...
    def reset(self, movie_id=None) -> None: ...
```

## 4. 가정

없음.

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2002-01 | 같은 영화 · 같은 질문을 다시 하면 P1 · P2 · 위키 호출 · 색인이 모두 0회다 | V4.2-3, V4.7-2 |
| AC-NF2002-02 | 다른 질문이라도 이미 검색한 검색어는 다시 검색하지 않는다 | V4.7-2 |
| AC-NF2002-03 | 이미 수집한 문서는 본문을 다시 받지 않는다 | V4.7-2 |
| AC-NF2002-04 | 검색이 실패한 검색어는 캐시에 기록되지 않아 다음에 다시 시도된다 | — |
| AC-NF2002-05 | 매니페스트가 깨져 있어도 앱이 멈추지 않는다 | — |
| AC-NF2002-06 | 앱을 다시 시작해도 캐시가 유지된다(파일 저장) | V4.2-3 |
| AC-NF2002-07 | 매니페스트 형식이 제공 `wiki_manifest.json`의 필드(`keywords`, `titles`, `page_ids`, `chunks`, `collected_at`)를 포함한다 | — |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2002-01 | 통합 | 같은 질문 2회 `collect` (가짜 LLM · HTTP) | 2회째 LLM 호출 0, HTTP 요청 0, `wiki_docs` 건수 불변, 진행 상태 `cache_hit` | 01 | `tests/integration/test_cache_path.py` |
| TC-NF2002-02 | 통합 | 질문 1의 검색어 `웜홀`, 질문 2의 검색어 `웜홀`, `중력` | 2회째 검색 요청은 `중력`만 | 02 | 〃 |
| TC-NF2002-03 | 통합 | 두 질문이 같은 문서를 고름 | 그 문서 본문 요청 1회 | 03 | 〃 |
| TC-NF2002-04 | 단위 | 검색 호출 실패 | `keywords`에 기록 안 됨 | 04 | `tests/unit/test_manifest.py` |
| TC-NF2002-05 | 단위 | 깨진 `manifest.json` | 백업 파일 생성, 빈 매니페스트로 동작 | 05 | 〃 |
| TC-NF2002-06 | 단위 | 기록 → 새 `Manifest` 객체로 다시 읽기 | 같은 내용 | 06 | 〃 |
| TC-NF2002-07 | 단위 | `"  인터스텔라의  블랙홀 "` vs `"인터스텔라의 블랙홀"` | 같은 질문으로 인식 | 01 | 〃 |
| TC-NF2002-08 | 통합 | 질문 캐시 적중 + `wiki_docs`에 그 영화 청크 0개 | 캐시 무시하고 재수집 | 01 | `tests/integration/test_cache_path.py` |
| TC-NF2002-09 | 단위 | 저장된 매니페스트 키 검사 | AC-07 필드 존재 | 07 | `tests/unit/test_manifest.py` |
| TC-NF2002-11 | 통합 | 고른 문서 하나가 `fetch_failed` · `index_failed` / 색인기 없음 | 검색어 · 질문 미기록(재질문 시 재시도), 성공 문서만 기록 / 아무것도 기록 안 함 | 01, 04 | `tests/integration/test_cache_path.py` |
| TC-NF2002-12 | 통합 | 청크 0개 + 매니페스트 기록 있음 + **새 질문** | 그 영화 매니페스트 초기화 후 문서 다시 수집 · 색인 | 01 | 〃 |
| TC-NF2002-13 | 단위 | 인스턴스 A가 읽은 뒤 B가 `reset` → A가 기록 | B의 초기화가 되살아나지 않음 | 06 | `tests/unit/test_manifest.py` |
| TC-NF2002-14 | 단위 | 구조가 틀린 JSON(`{"1": []}`, `{"1": {"keywords": "x"}}`) · 같은 시각 백업 2번 · 주입 날짜 | 백업 후 새로 시작 · 백업 파일 2개 · `collected_at`이 주입 날짜 | 05 | 〃 |
| TC-NF2002-10 | 수동 | Q1을 두 번 질문 | 두 번째에 "이미 수집한 질문입니다" 상태와 짧은 처리 시간 캡처 | 01 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-3, V4.7-2 | 같은 질문 2회 실제 실행 결과 — 색인기(F2005) 연결 후 다시 생성: 1회차 30초 수집 · 색인, 2회차 CACHE_HIT · 외부 호출 0 — 화면의 진행 상태 캡처는 F2012 이후 | `docs/verification/evidence/V4.2-3_cache.txt` |

## 8. 범위 밖

- 캐시 만료(TTL). 문서 개정 감지.
