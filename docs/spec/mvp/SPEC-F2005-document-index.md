# SPEC-F2005 위키백과 문서 색인 (RAG 2)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2005** 외부 문서 색인(RAG 2) (색인 · 필수) |
| 구분 | MVP |
| 상태 | Draft |
| 담당 모듈 | `movielab/index/doc_indexer.py`, `movielab/index/store.py`, `scripts/reindex_docs.py` |
| 선행 SPEC | SPEC-F2002, SPEC-F2004 |
| 관련 ISSUE | (생성 후 기입) |

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

### 3.3 재색인 규칙

- 같은 `(movie_id, page_id)`를 다시 색인할 때는 `where={"$and":[{"movie_id":…},{"page_id":…}]}`로 **기존 청크를 먼저 지운 뒤** 넣는다.
  (청크 크기를 바꿔 청크 수가 줄면 높은 순번의 옛 청크가 남기 때문)
- `scripts.reindex_docs`는 `data/raw/wiki/`의 저장 원문으로 `wiki_docs`를 다시 만든다(외부 호출 없음).
  `--chunk-size`, `--chunk-overlap` 인자는 **설정 파일 값을 일시적으로 덮어쓰는 실험용**이며, 출력에 사용한 값과 청크 수를 보여 준다 (V4.2-5).

### 3.4 인터페이스

```python
class DocIndexer:
    def __init__(self, store: VectorStore, settings): ...
    def index_document(self, doc: SourceDocument) -> int: ...      # 반환: 색인한 청크 수
    def delete_document(self, movie_id: str, page_id: str) -> int: ...
```

```text
python -m scripts.reindex_docs [--movie-id 157336] [--chunk-size 500 --chunk-overlap 100]
  → "chunk_size=500 overlap=100 → 문서 10건 / 청크 612개"
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

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2005-01 | 통합 | 합성 문서 3,000자, 설정 1000/200 | 청크 4개, 각 ≤ 1000자, ID `m:p:0..3` | 01 | `tests/integration/test_doc_index.py` |
| TC-F2005-02 | 통합 | 색인 후 두 컬렉션 건수 | `wiki_docs`만 늘고 `movie_meta`는 그대로 | 02 | 〃 |
| TC-F2005-03 | 통합 | 청크 메타데이터 검사 | §3.2 필수 필드 모두 존재, 타입 정확 | 03 | 〃 |
| TC-F2005-04 | 통합 | 영화 A · B가 같은 `page_id` 문서를 색인 | `count == A청크 + B청크`, 각 `movie_id` 필터로 조회 가능 | 04 | 〃 |
| TC-F2005-05 | 통합 | 설정 파일을 1000/200 → 500/100으로 바꾼 `tmp_settings`로 재색인 | 청크 수 증가, 메타데이터 `chunk_size == 500` | 05 | 〃 |
| TC-F2005-06 | 통합 | 500/100으로 색인 후 1000/200으로 재색인 | 순번이 큰 옛 청크 없음, 청크 수 == 새 분할 수 | 06 | 〃 |
| TC-F2005-07 | 단위 | `chunk_overlap = chunk_size` 설정 로드 | `SettingsError` | 07 | `tests/unit/test_config.py` |
| TC-F2005-08 | 단위 | `doc_indexer.py` 소스에 숫자 리터럴 `1000`, `200` 없음 | 통과 | 05 | `tests/unit/test_architecture.py` |
| TC-F2005-09 | 수동 | `reindex_docs`를 1000/200, 500/100으로 실행 | 두 청크 수를 비교한 출력 | 05 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-5 | 두 설정의 청크 수 비교 출력 캡처 + 설계문서에 표로 기록 | `docs/verification/screenshots/V4.2-5_chunk_settings.png` |

## 8. 범위 밖

- PDF 청킹(SPEC-F2016). 검색(SPEC-F2006).
