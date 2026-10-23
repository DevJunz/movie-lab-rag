# SPEC-F2005 위키백과 문서 색인 (RAG 2)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2005** 외부 문서 색인(RAG 2) (색인 · 필수) |
| 구분 | MVP |
| 상태 | In Progress (PR #32 리뷰 반영) |
| 담당 모듈 | `movielab/index/doc_indexer.py`, `movielab/index/store.py`, `scripts/reindex_docs.py` |
| 선행 SPEC | SPEC-F2002, SPEC-F2004 |
| 관련 ISSUE | #9 |

## 1. 요구사항 원문

> 수집한 문서를 청킹하여 별도의 컬렉션에 색인한다. 청크 크기와 중복 길이는 설정으로 조정할 수 있어야 한다.

명세서 3장 세부 조건:
- ◆ 수집한 문서 본문을 청크 크기와 중복 길이를 적용하여 분할해야 한다.
- ◆ 분할한 청크를 항목 메타데이터와 분리된 컬렉션에 색인해야 한다.
- ◆ 청크에는 문서 제목, 원문 출처, 관련 항목을 함께 저장해야 한다.
- ◆ 청크 식별자는 여러 항목이 같은 문서를 수집해도 서로 덮어쓰지 않도록 구성해야 한다.
- ◆ 청크 크기와 중복 길이는 코드가 아니라 설정으로 조정할 수 있어야 한다.

## 2. 도메인 표현 (Movie Lab)

수집한 위키백과 문서를 1,000자 청크 · 200자 중복으로 나눠 `wiki_docs` 컬렉션에 넣는다.
청크 ID는 `영화ID:문서ID:순번`이다. 시리즈물 · 같은 감독 작품처럼 여러 영화가 같은 문서를 공유해도 덮어쓰지 않는다.

## 3. 상세 명세

### 3.1 청킹

- `langchain_text_splitters.RecursiveCharacterTextSplitter(chunk_size, chunk_overlap)`.
  구분자 우선순위는 기본값(`"\n\n"`, `"\n"`, `" "`, `""`)을 쓴다 — 위키 평문은 문단이 `\n\n`으로 나뉜다.
- `chunk_size`, `chunk_overlap`은 `settings.chunking`에서만 읽는다. 코드에 숫자를 쓰지 않는다.
- 설정 검증: `0 <= chunk_overlap < chunk_size`가 아니면 `SettingsError`.

### 3.2 청크 ID · 메타데이터

- ID: `f"{movie_id}:{page_id}:{seq}"`, `seq`는 0부터. `movie_id` · `page_id`는 문자열로 정규화한다.
- 메타데이터: [01-architecture.md §5.3 `wiki_docs`](../01-architecture.md#53-메타데이터-필드) 전부.
  필수: `movie_id`, `page_id`, `title`, `url`, `related_movie`, `search_query`, `collected_at`, `is_item_doc`,
  `chunk_index`, `chunk_size`, `chunk_overlap`, `source_kind="wiki"`, `source_type="위키백과"`, `license="CC BY-SA 4.0"`.
- `source_type` 라벨은 `DomainProfile.doc_source_label`을 container가 넘긴다. `DocIndexer`는 기본값 없이 필수 인자로 받는다 (`index/`에 도메인 문구를 두지 않는다, NF2005).

### 3.3 재색인 규칙

- 같은 `(movie_id, page_id)`를 다시 색인할 때는 **새 청크를 먼저 `upsert`하고**, 그다음 이번 분할에 없는 옛 청크 ID
  (`where={"$and":[{"movie_id":…},{"page_id":…}]}`로 찾은 ID 가운데 새 ID 집합에 없는 것)만 지운다.
  - 청크 크기를 바꿔 청크 수가 줄어도 높은 순번의 옛 청크가 남지 않는다 (AC-06).
  - 임베딩(쓰기) 단계에서 실패하면 옛 청크가 그대로 남는다 — 문서가 색인에서 사라지지 않는다 (AC-09).
- `scripts.reindex_docs`는 `data/raw/wiki/`의 저장 원문으로 `wiki_docs`를 다시 만든다(외부 호출 없음).
  - `--chunk-size`, `--chunk-overlap` 인자는 **설정 파일 값을 일시적으로 덮어쓰는 실험용**이다.
    덮어쓴 결과에도 설정과 같은 검증 규칙(`config.chunking_ok(size, overlap)`: `size ≥ 1`, `0 ≤ overlap < size`)을 적용하고,
    어기면 색인 전에 인자 오류(`REINDEX_BAD_CHUNKING`, 종료 코드 2)로 끝낸다 (AC-10).
  - `services.indexing.reindex_documents`는 문서별로 실패를 격리한다: 잘못된 키(`openai.AuthenticationError` ·
    `PermissionDeniedError`)는 `InvalidApiKeyError`로 바꿔 즉시 중단하고(키 안내 문구), 그 밖의 오류는 로그에 남기고
    실패 문서 수로 집계한 뒤 다음 문서로 넘어간다 (AC-11).
  - 전체 재색인이면 저장 원문이 없는 `(movie_id, page_id)`의 청크를 지운다. `--movie-id`를 주면 그 영화 범위에서만 지운다 (AC-12).
  - 출력: 사용한 값, 문서 수, 이번에 색인한 청크 수, 지운 문서 수, 실패 문서 수, 재색인 후 컬렉션 전체 청크 수 (V4.2-5).
  - 예외 원문은 화면에 내보내지 않는다 — 안내 문구만 출력하고 원문은 로그로 (NF2004).
- 매니페스트(NF2002)의 `chunks`는 **수집 당시 색인한 청크 수의 기록**이다. 재색인은 매니페스트를 갱신하지 않는다
  (캐시 판단은 `chunks` 값이 아니라 `wiki_docs`에 그 영화 청크가 있는지로 한다).

### 3.4 연결

- `Collector`(F2004)의 `indexer`로 `DocIndexer.index_document`를, `has_chunks`(NF2002)로 `VectorStore.has_where(docs, {"movie_id": …})`를 container에서 연결한다.
  `has_where`는 `limit=1`로 한 건만 확인한다 — 질문마다 그 영화의 청크 ID 전체를 읽지 않는다 (AC-08).
- 계층 규칙상 `scripts.reindex_docs`는 `services/indexing.reindex_documents(documents, indexer)`를 쓰고, 저장 원문은 `Services.raw_store`(container)에서 얻는다.
- 설정 검증: `chunk_size`는 1 이상 정수, `chunk_overlap`은 0 이상 정수이고 `chunk_size`보다 작아야 한다(PDF 값도 같은 규칙). 어기면 `SettingsError`.

### 3.5 인터페이스

```python
class DocIndexer:
    def __init__(self, store: VectorStore, *, source_type: str,
                 chunk_size: int | None = None, chunk_overlap: int | None = None): ...
        # 청크 값을 주지 않으면 settings.chunking 값. 준 값이 chunking_ok를 어기면 ValueError
    def index_document(self, doc: SourceDocument) -> int: ...      # 반환: 색인한 청크 수
    def delete_document(self, movie_id: str, page_id: str) -> int: ...
    def indexed_pages(self, movie_id: str | None = None) -> set[tuple[str, str]]: ...

def reindex_documents(documents, indexer, *, movie_id: str | None = None) -> ReindexReport: ...
    # ReindexReport(documents, chunks, failed, removed, total_chunks)
```

```text
python -m scripts.reindex_docs [--movie-id 157336] [--chunk-size 500 --chunk-overlap 100]
  → "chunk_size=500 overlap=100 → 문서 10건 / 청크 612개 (컬렉션 전체 612개)"
```

## 4. 가정

| ID | 내용 |
|---|---|
| D-04 | 1,000자 / 200자 (사용자 확인) |
| A-19 | 코사인 거리 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2005-01 | 수집 문서는 설정값으로 청킹되고 각 청크는 `chunk_size` 이하이다 | V4.2-5 |
| AC-F2005-02 | 청크는 `movie_meta`와 다른 컬렉션 `wiki_docs`에 들어간다 | — |
| AC-F2005-03 | 각 청크 메타데이터에 문서 제목 · 원문 URL · 관련 영화(`movie_id`, `related_movie`)가 있다 | — |
| AC-F2005-04 | 영화 A와 B가 같은 문서를 수집하면 두 영화의 청크가 모두 남는다 (덮어쓰기 없음) | — |
| AC-F2005-05 | 설정 파일의 청크 크기 · 중복을 바꿔 재색인하면 청크 수가 달라진다. 코드는 바꾸지 않는다 | V4.2-5 |
| AC-F2005-06 | 같은 문서를 더 큰 청크로 재색인해도 옛 청크가 남지 않는다 | V4.2-5 |
| AC-F2005-07 | `chunk_overlap >= chunk_size` 설정은 시작 시 거부된다 | — |
| AC-F2005-08 | container의 수집기는 수집 문서를 `wiki_docs`에 청크로 색인하고, 그 영화 청크가 없으면 캐시를 믿지 않는다 | V4.2-3 |
| AC-F2005-09 | 재색인 중 임베딩이 실패해도 그 문서의 옛 청크는 남는다 | — |
| AC-F2005-10 | `reindex_docs`의 청크 인자가 검증 규칙을 어기면 색인 전에 안내 문구로 거부한다 (라이브러리 원문 출력 없음) | — |
| AC-F2005-11 | 재색인에서 잘못된 키는 키 안내로, 다른 문서 오류는 그 문서만 실패로 집계하고 나머지는 계속 색인한다 | — |
| AC-F2005-12 | 전체 재색인 후 저장 원문이 없는 문서의 청크는 남지 않는다 | V4.2-5 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2005-01 | 통합 | 합성 문서 3,000자, 설정 1000/200 | 청크 정확히 4개, 각 ≤ 1000자, ID `m:p:0..3` | 01 | `tests/integration/test_doc_index.py` |
| TC-F2005-02 | 통합 | 색인 후 두 컬렉션 건수 | `wiki_docs`만 늘고 `movie_meta`는 그대로 | 02 | 〃 |
| TC-F2005-03 | 통합 | 청크 메타데이터 검사 | §3.2 필수 필드 모두 존재, 타입 정확 | 03 | 〃 |
| TC-F2005-04 | 통합 | 영화 A · B가 같은 `page_id` 문서를 색인 | `count == A청크 + B청크`, 각 `movie_id` 필터로 조회 가능 | 04 | 〃 |
| TC-F2005-05 | 통합 | 설정 파일을 1000/200 → 500/100으로 바꾼 `tmp_settings`로 재색인 | 청크 수 증가, 메타데이터 `chunk_size == 500` | 05 | 〃 |
| TC-F2005-06 | 통합 | 500/100으로 색인 후 1000/200으로 재색인 | 순번이 큰 옛 청크 없음, 청크 수 == 새 분할 수 | 06 | 〃 |
| TC-F2005-07 | 통합 | `chunk_overlap = chunk_size` 등 잘못된 설정 로드 | `SettingsError` | 07 | 〃 |
| TC-F2005-08 | 단위 | `doc_indexer.py` 소스에 숫자 리터럴 `1000`, `200` 없음 | 통과 | 05 | `tests/unit/test_architecture.py` |
| TC-F2005-09 | 통합 | `reindex_docs`를 1000/200, 500/100으로 실행 (실제 수치는 V4.2-5 증빙) | 출력에 사용 값, 500/100 청크 수가 더 많음 | 05 | `tests/integration/test_scripts.py` |
| TC-F2005-10 | 통합 | container 수집기로 수집 → 같은 질문 → `wiki_docs` 삭제 후 같은 질문 | 청크 수 == 보고 수, 두 번째는 캐시 적중, 세 번째는 다시 수집 | 08 | `tests/integration/test_collect_index.py` |
| TC-F2005-11 | 통합 | A · B가 공유한 문서에서 A만 `delete_document` | A 청크만 지워지고 B는 남음 | 04 | `tests/integration/test_doc_index.py` |
| TC-F2005-12 | 통합 | 색인 후 임베딩이 실패하는 상태에서 같은 문서를 다른 크기로 재색인 | 예외, 옛 청크 ID · 건수 그대로 | 09 | 〃 |
| TC-F2005-13 | 통합 | `reindex_docs --chunk-size 500 --chunk-overlap 500`, `--chunk-size 100`(설정 중복 200) | 종료 코드 2, 안내 문구, 영어 원문 없음, 색인 변화 없음 | 10 | `tests/integration/test_scripts.py` |
| TC-F2005-14 | 통합 | `reindex_documents`: 한 문서만 일반 오류 / 인증 오류 | 나머지 색인 · `failed == 1` / `InvalidApiKeyError` | 11 | `tests/integration/test_doc_index.py` |
| TC-F2005-15 | 통합 | 원문 2건 색인 후 원문 1건을 지우고 전체 재색인 · `--movie-id` 범위 재색인 | 지운 문서 청크 없음, `removed == 1`; 다른 영화 청크는 범위 밖이면 유지 | 12 | 〃 |
| TC-F2005-16 | 단위 | `VectorStore.has_where` | 청크가 있으면 참, 없거나 컬렉션이 없으면 거짓 | 08 | 〃 |
| TC-F2005-17 | 단위 | `DocIndexer`에 `source_type` 없이 생성 | `TypeError` | — | 〃 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-5 | 실제 수집 원문 12건을 1000/200 · 500/100 · 1500/300으로 재색인한 청크 수(302 · 630 · 200) + 설계문서에 표로 기록 | `docs/verification/evidence/V4.2-5_chunk_settings.txt` |

## 8. 범위 밖

- PDF 청킹(SPEC-F2016). 검색(SPEC-F2006).
