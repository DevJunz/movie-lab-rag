# SPEC-F2002 영화 메타데이터 색인 (RAG 1)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2002** 메타데이터 색인(RAG 1) (색인 · 필수) |
| 구분 | MVP |
| 상태 | In Progress |
| 담당 모듈 | `movielab/index/store.py`, `movielab/index/meta_indexer.py`, `scripts/index_meta.py` |
| 선행 SPEC | SPEC-F2001 |
| 관련 ISSUE | #4 |

## 1. 요구사항 원문

> 항목 텍스트를 임베딩하여 Vector DB 컬렉션에 색인한다.

명세서 3장 세부 조건:
- ◆ 구성한 텍스트를 임베딩하여 Vector DB 컬렉션에 색인해야 한다.
- ◆ 색인 결과로 저장된 청크 수를 확인할 수 있어야 한다.
- ◆ 색인 작업을 다시 실행해도 같은 항목이 중복 저장되지 않아야 한다.

## 2. 도메인 표현 (Movie Lab)

영화 964편의 색인 텍스트를 `movie_meta` 컬렉션에 영화당 청크 1개로 넣는다. 화면 사이드바에 현재 색인 건수를 항상 보인다.

## 3. 상세 명세

### 3.1 동작

1. `load_items()`(F2001)로 `ItemRecord` 목록을 얻는다.
2. 컬렉션 `settings.collections.meta`(기본 `movie_meta`)를 가져오거나 만든다(코사인 거리).
3. `ids = [item_id]`로 **upsert** 한다. 같은 ID는 덮어쓰기만 일어나므로 재실행해도 건수가 늘지 않는다.
4. 임베딩 호출은 배치(기본 100건)로 나눠 보낸다. 배치 하나가 실패하면 재시도 후에도 실패한 배치를 보고하고, 이미 들어간 배치는 유지한다(재실행으로 이어서 채울 수 있다).
5. `--rebuild` 옵션은 컬렉션을 지우고 처음부터 만든다.
6. 끝나면 `로드 N건 / 색인 M건 / 건너뜀 K건`을 출력한다. `N - K == M`이 아니면 종료 코드 1.

### 3.2 인터페이스

```python
# movielab/index/store.py
class VectorStore:
    def __init__(self, client, embeddings, settings): ...
    def collection(self, name: str): ...                 # langchain_chroma.Chroma 래퍼
    def count(self, name: str) -> int: ...               # 저장된 청크 수
    def get_by_ids(self, name: str, ids: list[str]) -> list[Document]: ...

# movielab/index/meta_indexer.py
def index_items(store: VectorStore, items: list[ItemRecord], batch_size: int = 100) -> IndexReport: ...
```

```text
python -m scripts.index_meta              # 색인 (재실행 안전)
python -m scripts.index_meta --rebuild    # 컬렉션을 지우고 다시 색인
python -m scripts.index_meta --show 157336  # 색인 텍스트 출력 (F2001)
python -m scripts.index_meta --count      # 현재 건수만 출력
```

- 계층 규칙상 스크립트는 `index`를 직접 부르지 않는다. `services/indexing.py`의 `index_catalog(catalog, store, rebuild=False) -> IndexReport`가 F2001 `Catalog`와 `VectorStore`를 잇는다. 스크립트는 `Services.store` · `Services.catalog`(container)로 얻는다.
- `VectorStore`는 임베딩을 **처음 필요할 때** 만든다(`embeddings`에 객체 또는 객체를 돌려주는 함수를 받는다). 그래서 `--count` · `--show`는 GMS 키 없이 동작한다.
- `IndexReport`: `loaded`(로드 원소 수 = 항목 + 건너뜀), `skipped`, `indexed`(색인 후 컬렉션 건수), `failed_batches`(실패 배치 번호), `ok`(= `loaded - skipped == indexed` 이고 실패 배치 없음).
- 메타데이터 필드는 [01-architecture.md §5.3](../01-architecture.md#53-메타데이터-필드)을 따른다.
- UI 사이드바는 `services.health`를 통해 `movie_meta` · `wiki_docs` 건수를 표시한다(F2009 화면, F2012 안내와 연결).

## 4. 가정

| ID | 내용 |
|---|---|
| A-19 | 코사인 거리 |
| — | 임베딩 배치 크기 100 (설정 없이 상수. 바꿔야 하면 settings로 옮긴다) |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2002-01 | 색인 후 `movie_meta` 건수 == 로드한 영화 수 − 건너뛴 수 | V4.1-1 |
| AC-F2002-02 | 색인을 두 번 실행해도 건수가 같다 | V4.1-2 |
| AC-F2002-03 | 청크 ID는 `movie_id`이고, `get_by_ids([movie_id])`로 바로 꺼낼 수 있다 | (F2006 선행) |
| AC-F2002-04 | 저장된 메타데이터에 `source_kind="meta"`, `source_type="영화 메타데이터"`, `url=tmdb_url`, `year`(int), `original_language`가 있다 | (F2007, F2011 선행) |
| AC-F2002-05 | 스크립트와 UI에서 현재 색인 건수를 확인할 수 있다 | V4.1-1 |
| AC-F2002-06 | 목록 값이 Chroma 메타데이터에 문자열로 저장된다(목록 그대로 넣지 않는다) | — |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2002-01 | 통합 | 합성 12편을 `FakeEmbeddings` + 임시 Chroma에 색인 | `count == 12` | 01 | `tests/integration/test_meta_index.py` |
| TC-F2002-02 | 통합 | 같은 12편을 두 번 색인 | 두 번째 후에도 `count == 12` | 02 | 〃 |
| TC-F2002-03 | 통합 | 한 편의 줄거리를 바꿔 재색인 | `count` 그대로, 해당 문서 본문만 바뀜 | 02, 03 | 〃 |
| TC-F2002-04 | 통합 | `get_by_ids(["157336"])` | 문서 1개, 메타데이터 필드 검증 | 03, 04, 06 | 〃 |
| TC-F2002-05 | 통합 | `--rebuild` 후 건수 | 12 (지운 뒤 다시 채움) | 01 | `tests/integration/test_scripts.py` |
| TC-F2002-06 | 통합 | 임베딩이 두 번째 배치에서 예외 | 첫 배치는 남고 보고서에 실패 배치 표시, 종료 코드 1 | 01 | 〃 |
| TC-F2002-07 | live | 실제 GMS 임베딩으로 영화 3편 색인 | `count == 3` | 01 | `tests/live/test_live_index.py` |
| TC-F2002-08 | 수동 | 실제 964편 색인 2회 실행 | 두 번 모두 `색인 964건` | 01, 02, 05 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.1-1 | 색인 출력 + 사이드바 건수 캡처 | `docs/verification/screenshots/V4.1-1_meta_count.png` |
| V4.1-2 | 두 번째 실행 출력 캡처 | `docs/verification/screenshots/V4.1-2_reindex.png` |

## 8. 범위 밖

- 위키 문서 색인(SPEC-F2005). 조건 탐색 필터 사용(SPEC-F2011).
