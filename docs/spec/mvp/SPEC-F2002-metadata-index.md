# SPEC-F2002 영화 메타데이터 색인 (RAG 1)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2002** 메타데이터 색인(RAG 1) (색인 · 필수) |
| 구분 | MVP |
| 상태 | Done (live · 수동 검증 대기) |
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

1. `Catalog.items()`(F2001)로 `ItemRecord` 목록을 얻는다.
2. **임베딩(=GMS 키)을 먼저 준비한다.** 키가 없으면 여기서 안내 오류로 끝나고, 기존 색인은 그대로 둔다.
3. 컬렉션 `settings.collections.meta`(기본 `movie_meta`)를 가져오거나 만든다(코사인 거리). `--rebuild`면 2 다음에 지우고 다시 만든다.
4. `Document.id = item_id`로 **upsert** 한다. 같은 ID는 덮어쓰기만 일어나므로 재실행해도 건수가 늘지 않는다.
5. 임베딩은 배치(`indexing.batch_size`, 기본 100)로 나눠 보낸다. 배치가 실패하면 `indexing.retry_wait_sec`만큼 기다린 뒤 `indexing.retries`번 재시도한다.
   - **재시도하지 않는 오류**: 사용자 안내 오류(`MovieLabUserError`), 인증 · 권한 · 요청 형식 오류(OpenAI `AuthenticationError` · `PermissionDeniedError` · `BadRequestError` · `NotFoundError`), `ValueError` · `TypeError`. 다시 해도 같은 결과이므로 즉시 전파한다.
   - 재시도 후에도 실패한 배치만 보고하고, 이미 들어간 배치는 유지한다(재실행으로 이어서 채울 수 있다).
6. 모든 배치가 성공하면, **이번에 로드하지 않은 ID의 문서(고아 문서)를 지운다** — 데이터에서 빠진 영화가 검색에 남지 않게. 실패 배치가 있으면 지우지 않는다.
7. 끝나면 `로드 N건 / 색인 M건 / 건너뜀 K건`을 출력한다. `M`은 **로드한 ID 중 컬렉션에 있는 수**다. `N - K == M`이 아니거나 실패 배치가 있으면 종료 코드 1.

### 3.2 인터페이스

```python
# movielab/index/store.py
class VectorStore:
    def __init__(self, client, settings, *, embeddings=None, embeddings_factory=None): ...  # 팩토리는 한 번만 호출
    settings                                               # 컬렉션 이름 등은 여기서 읽는다
    embeddings                                             # 처음 접근할 때 해결 (키 검사 시점)
    def collection(self, name: str): ...                   # langchain_chroma.Chroma 래퍼
    def count(self, name: str) -> int: ...                 # 저장된 청크 수 (임베딩 불필요)
    def ids(self, name: str) -> list[str]: ...             # 저장된 청크 ID (임베딩 불필요)
    def get_by_ids(self, name: str, ids: list[str]) -> list[Document]: ...
    def upsert(self, name: str, documents: list[Document]) -> None: ...  # ID는 Document.id
    def delete_ids(self, name: str, ids: list[str]) -> None: ...
    def delete_collection(self, name: str) -> None: ...

# movielab/index/meta_indexer.py
def index_items(store, items, *, collection, batch_size, retries, retry_wait_sec, sleep=time.sleep) -> list[int]:
    """반환: 재시도 후에도 실패한 배치 번호(0부터)"""

# movielab/services/indexing.py
def index_catalog(catalog, store, *, rebuild=False, batch_size=None, sleep=time.sleep) -> IndexReport: ...
```

```text
python -m scripts.index_meta              # 색인 (재실행 안전)
python -m scripts.index_meta --rebuild    # 키 확인 후 컬렉션을 지우고 다시 색인
python -m scripts.index_meta --show 157336  # 색인 텍스트 출력 (F2001)
python -m scripts.index_meta --count      # 현재 건수만 출력 (키 없이 가능)
python -m scripts.index_meta --batch-size 50  # 배치 크기를 이번 실행만 바꿈 (1 이상 정수)
```

- 계층 규칙상 스크립트는 `index`를 직접 부르지 않는다. `services/indexing.py`의 `index_catalog`가 F2001 `Catalog`와 `VectorStore`를 잇는다. 스크립트는 `Services.store` · `Services.catalog`(container)로 얻는다.
- `VectorStore`는 임베딩을 **처음 필요할 때** 만든다. 그래서 `--count` · `--show`는 GMS 키 없이 동작한다. 객체와 팩토리는 **서로 다른 인자**로 받는다(타입으로 추측하지 않음). 팩토리는 한 번만 호출하고 결과를 캐시한다.
- 배치 크기 · 재시도 횟수 · 재시도 대기는 `config/settings.json`의 `indexing` 묶음에서 읽는다(A-21). `batch_size < 1` 또는 `retries < 0`이면 `SettingsError`.
- `IndexReport`: `loaded`(로드 원소 수 = 항목 + 건너뜀), `skipped`, `indexed`(로드한 ID 중 컬렉션에 있는 수), `removed`(지운 고아 문서 수), `failed_batches`, `ok`.
- 불일치 안내에는 `--rebuild`로 다시 만들 수 있다는 해결 방법을 함께 보인다.
- 메타데이터 필드는 [01-architecture.md §5.3](../01-architecture.md#53-메타데이터-필드)을 따른다.
- UI 사이드바는 `services.health`를 통해 `movie_meta` · `wiki_docs` 건수를 표시한다(F2009 화면, F2012 안내와 연결).

## 4. 가정

| ID | 내용 |
|---|---|
| A-19 | 코사인 거리 |
| A-21 | 메타 색인 배치 100건, 배치당 재시도 1회, 재시도 전 2초 대기 (`settings.indexing`) |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2002-01 | 색인 후 `movie_meta` 건수 == 로드한 영화 수 − 건너뛴 수 | V4.1-1 |
| AC-F2002-02 | 색인을 두 번 실행해도 건수가 같다 | V4.1-2 |
| AC-F2002-03 | 청크 ID는 `movie_id`이고, `get_by_ids([movie_id])`로 바로 꺼낼 수 있다 | (F2006 선행) |
| AC-F2002-04 | 저장된 메타데이터에 `source_kind="meta"`, `source_type="영화 메타데이터"`, `url=tmdb_url`, `year`(int), `original_language`가 있고, 컬렉션은 코사인 거리다 | (F2007, F2011 선행) |
| AC-F2002-05 | 스크립트와 UI에서 현재 색인 건수를 확인할 수 있다(스크립트는 키 없이) | V4.1-1 |
| AC-F2002-06 | 목록 값이 Chroma 메타데이터에 문자열로 저장된다(목록 그대로 넣지 않는다) | — |
| AC-F2002-07 | 키가 없거나 임베딩이 실패해도 기존 색인을 잃지 않는다(`--rebuild` 포함). 복구할 수 없는 오류는 재시도하지 않고 바로 안내한다 | — |
| AC-F2002-08 | 데이터에서 빠진 항목의 문서는 다음 색인 후 남지 않는다 | V4.1-1 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2002-01 | 통합 | 합성 12편을 `FakeEmbeddings` + 임시 Chroma에 색인 | `count == 12` | 01 | `tests/integration/test_meta_index.py` |
| TC-F2002-02 | 통합 | 같은 12편을 두 번 색인 | 두 번째 후에도 `count == 12` | 02 | 〃 |
| TC-F2002-03 | 통합 | 한 편의 줄거리를 바꿔 재색인 | `count` 그대로, 해당 문서 본문만 바뀜 | 02, 03 | 〃 |
| TC-F2002-04 | 통합 | `get_by_ids(["157336"])` | 문서 1개, 메타데이터 필드 검증 | 03, 04, 06 | 〃 |
| TC-F2002-05 | 통합 | 스크립트: 색인 · 재실행 · `--count` · `--rebuild` | 매번 12, `--count` 출력 | 01, 02, 05 | `tests/integration/test_scripts.py` |
| TC-F2002-06 | 통합 | 임베딩이 특정 배치에서 계속 예외 (서비스 · 스크립트) | 나머지 배치는 남고 실패 배치 보고, 재시도 전 대기, 종료 코드 1 | 01, 07 | 〃 |
| TC-F2002-07 | live | 실제 GMS 임베딩으로 영화 3편 색인 | `count == 3` | 01 | `tests/live/test_live_index.py` |
| TC-F2002-08 | 수동 | 실제 964편 색인 2회 실행 | 두 번 모두 `색인 964건` | 01, 02, 05 | 증빙 파일 |
| TC-F2002-09 | 통합 | 컬렉션 거리 설정 확인 | `cosine` | 04 | `tests/integration/test_meta_index.py` |
| TC-F2002-10 | 통합 | 키 없이 `count` · `get_by_ids` · `--count` | 0 · `[]` · 출력, 예외 없음 | 05 | `test_meta_index.py`, `test_scripts.py` |
| TC-F2002-11 | 통합 | 12편 색인 후 키 없이 색인 · `--rebuild` | 키 안내 문구, **건수 12 유지** | 07 | `tests/integration/test_scripts.py` |
| TC-F2002-12 | 통합 | 복구 불가 오류(`ValueError`, 인증 오류) | 재시도 0회로 즉시 전파 | 07 | `tests/unit/test_meta_indexer.py` |
| TC-F2002-13 | 통합 | 12편 색인 후 1편이 빠진 데이터로 재색인 | 11건, 빠진 ID 없음, `removed == 1`, `ok` | 08 | `tests/integration/test_meta_index.py` |
| TC-F2002-14 | 단위 | `--batch-size 0` · `-5`, 설정 `batch_size: 0` | 인자 오류(종료 코드 2) · `SettingsError` | 01 | `test_scripts.py`, `tests/unit/test_config.py` |
| TC-F2002-15 | 단위 | `Embeddings`를 상속하지 않은 덕 타이핑 임베딩 주입, 컬렉션 2개 사용 | 호출되지 않고 그대로 사용 | 05 | `tests/unit/test_store.py` |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.1-1 | 색인 출력(+ 사이드바 건수 캡처는 F2009 이후) | `docs/verification/evidence/V4.1-1_meta_count.txt` |
| V4.1-2 | 두 번째 실행 출력 | `docs/verification/evidence/V4.1-2_reindex.txt` |

## 8. 범위 밖

- 위키 문서 색인(SPEC-F2005). 조건 탐색 필터 사용(SPEC-F2011).
