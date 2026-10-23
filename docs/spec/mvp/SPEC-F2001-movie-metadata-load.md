# SPEC-F2001 영화 메타데이터 적재

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2001** 항목 메타데이터 적재 (데이터 · 필수) |
| 구분 | MVP |
| 상태 | Done |
| 담당 모듈 | `movielab/data/movies.py`, `movielab/data/domain_movie.py` |
| 선행 SPEC | SPEC-NF2005, SPEC-NF2003 |
| 관련 ISSUE | #3 |

## 1. 요구사항 원문

> 선택한 도메인의 항목 목록을 로드하고 항목 1건을 하나의 색인 텍스트로 구성한다.

명세서 3장 세부 조건:
- ◆ 선택한 도메인의 항목 메타데이터를 로드할 수 있어야 한다.
- ◆ 항목 1건의 메타데이터를 검색에 사용할 하나의 텍스트로 구성해야 한다.
- ◆ 항목은 약 100건 이상이어야 한다.

## 2. 도메인 표현 (Movie Lab)

`movies.json`의 영화 964편을 읽고, 영화 1편을 색인 텍스트 1개로 만든다.

## 3. 상세 명세

### 3.1 입력 · 출력

- 입력: `settings.paths.movies` (기본 `영화도메인_데이터_배포용/movies.json`, UTF-8)
- 출력: `list[ItemRecord]` — 파일 순서를 유지한다.

### 3.2 색인 텍스트 구성

사용자가 영화를 찾을 단서(제목 · 원제 · 연도 · 장르 · 감독 · 출연 · 국가 · 줄거리)를 모두 넣는다.
줄거리를 넣어야 "우주를 배경으로 한 가족 영화" 같은 조건 검색(F2011)이 걸린다.
평점 · 투표 수 · 상영 시간은 의미 검색에 도움이 되지 않으므로 텍스트에서 빼고 메타데이터 필드로만 둔다.

```text
제목: 인터스텔라 (2014)
원제: Interstellar
장르: 모험, 드라마, SF
감독: 크리스토퍼 놀란
출연: 매튜 매커너히, 앤 해서웨이, 마이클 케인, 제시카 차스테인, 케이시 애플렉
제작 국가: United Kingdom, United States of America
원어: en (해외 영화)
줄거리: 세계 각국의 정부와 경제가 완전히 붕괴된 미래가 다가온다. …
```

규칙:
- 색인 텍스트는 **8줄**이다(연도는 제목 줄에 들어간다).
- 목록 필드는 `", "`로 잇는다. 빈 목록 · `null` · 공백뿐인 값은 `정보 없음`으로 쓴다 (실데이터: `1084390` 소주전쟁의 감독).
- `원어` 줄은 언어 코드를 소문자로 정규화한 뒤 `ko`이면 `ko (한국 영화)`, 다른 코드면 `<코드> (해외 영화)`, 값이 없으면 `정보 없음`으로 쓴다 — "한국 영화" 조건 검색용.
- 줄 순서와 라벨은 데이터 준비 영역 `data/movies.py`에 정의하고 `to_index_text(movie) -> str`가 만든다. `DomainProfile.to_index_text` · `DomainProfile.load_items`로 노출하며, container는 **프로필의 로더**로 `Catalog`를 만든다(다른 프로필을 주입하면 다른 데이터를 읽는다).
- 필수 필드(`movie_id`, `title`, `year`, `overview`)가 없거나 공백뿐인 원소, **숫자 필드(`year`, `runtime`, `vote_average`)를 숫자로 바꿀 수 없는 원소**는 건너뛰고 경고 로그를 남긴다. 건너뛴 수를 반환 정보에 포함한다. 한 편의 잘못된 값 때문에 전체 로드가 실패하지 않는다.
- 연도는 정수로 정규화해 제목 줄과 `ItemRecord.year`에 같은 값을 쓴다(`2014.0` → `2014`).
- 파일이 JSON 배열이 아니면 `DataNotFoundError`가 아니라 `DataFormatError`(안내 코드 `DATA_INVALID`).
- 스크립트의 사용자 문구는 `core/messages.py`에서 가져오고, 예상하지 못한 오류도 traceback 없이 안내 문구만 출력한다(NF2004).
- `movie_id`는 문자열로 정규화한다. 중복 `movie_id`가 있으면 첫 번째만 쓰고 경고한다.

### 3.3 인터페이스

```python
# movielab/data/movies.py
def load_movies(path: Path) -> list[dict]: ...                 # 원본 그대로
def to_index_text(movie: dict) -> str: ...                     # 3.2 규칙
def to_item_record(movie: dict) -> ItemRecord: ...             # 메타데이터 필드는 01-architecture §5.3
def load_items(path: Path) -> LoadResult:                      # items: list[ItemRecord], skipped: int
```

```python
# movielab/services/catalog.py — 계층 규칙상 services · scripts · ui는 data를 직접 import 하지 않는다
class Catalog:
    def __init__(self, loader: Callable[[], LoadResult]): ...   # container가 data.movies.load_items를 주입
    def items(self) -> list[ItemRecord]: ...                     # 처음 한 번만 로드
    def get(self, item_id: str) -> ItemRecord | None: ...
    @property
    def skipped(self) -> int: ...
```

- `ItemRecord` · `LoadResult`는 `movielab/core/types.py`에 둔다.
- `Services.catalog`(container)로 얻는다. 영화 데이터 팩이 없으면 `items()`가 `DataNotFoundError`(안내 코드 `DATA_MISSING`)를 던진다.
- `python -m scripts.index_meta --show <movie_id>`는 해당 영화의 색인 텍스트를 출력한다 (V4.1-3 증빙). 색인(F2002) 기능은 SPEC-F2002에서 이 스크립트에 더한다.

## 4. 가정

| ID | 내용 |
|---|---|
| — | 이 SPEC에서 새로 둔 가정 없음. 데이터 출처 이용 조건은 A-15 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2001-01 | 실제 `movies.json`을 로드하면 964건이 나오고, 모두 `ItemRecord`로 바뀐다 (100건 이상 조건 충족) | V4.1-1 |
| AC-F2001-02 | 영화 1편의 색인 텍스트에 제목 · 원제 · 연도 · 장르 · 감독 · 출연 · 제작 국가 · 원어 · 줄거리가 모두 들어간다 | V4.1-3 |
| AC-F2001-03 | 빈 목록 필드는 `정보 없음`으로 표기되고 예외가 나지 않는다 | — |
| AC-F2001-04 | 필수 필드가 빠진 원소는 건너뛰고 `skipped`로 센다 | — |
| AC-F2001-05 | `movie_id`는 항상 `str`이다 | — |
| AC-F2001-06 | 영화 도메인 고유 라벨은 `movielab/data/` 밖에 없다 | (NF2005) |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2001-01 | 단위 | 합성 영화 1편으로 `to_index_text` 호출 | 8개 라벨 줄이 순서대로 있고 값이 맞다 | 02 | `tests/unit/test_movies.py` |
| TC-F2001-02 | 단위 | `director: []`인 영화 | `감독: 정보 없음` | 03 | 〃 |
| TC-F2001-03 | 단위 | `original_language: "ko"` / `"en"` | `ko (한국 영화)` / `en (해외 영화)` | 02 | 〃 |
| TC-F2001-04 | 단위 | `overview`가 없는 원소 1개가 섞인 목록 | `skipped == 1`, 나머지는 정상 | 04 | 〃 |
| TC-F2001-05 | 단위 | `movie_id`가 숫자 `123`인 원소 | `item_id == "123"` | 05 | 〃 |
| TC-F2001-06 | 통합 | 제공 `movies.json`이 있으면 로드 (없으면 `skip`) | 964건, `skipped == 0` | 01 | `tests/integration/test_movies_real.py` |
| TC-F2001-07 | 수동 | `python -m scripts.index_meta --show 157336` | §3.2 예시와 같은 텍스트 출력 | 02 | 스크린샷 |
| TC-F2001-09 | 단위 | `Catalog`에 가짜 로더 주입: `items()` 2번 · `get()` | 로더는 1번만 호출, 없는 ID는 `None` | 01 | `tests/unit/test_catalog.py` |
| TC-F2001-10 | 통합 | `tmp_settings`로 `scripts.index_meta --show 157336` 실행 / 데이터 파일 없음 | 8줄 색인 텍스트(라벨 목록 정확히 일치) 출력 / 안내 문구 · 종료 코드 1 | 02 | `tests/integration/test_scripts.py` |
| TC-F2001-11 | 단위 | `director: [null]` · `original_language` 없음 · `"KO"` · 공백뿐인 `title` · `year: "미상"` · `runtime: "169분"` · `year: 2014.0` | 정보 없음 / 정보 없음 / 한국 영화 / 건너뜀 / 건너뜀 / 건너뜀 / `2014` | 03, 04 | `tests/unit/test_movies.py` |
| TC-F2001-12 | 통합 | 깨진 JSON · 배열이 아닌 JSON · 잘못된 설정 파일로 `--show` | 안내 문구, traceback 없음, 종료 코드 1 | 02 | `tests/integration/test_scripts.py` |
| TC-F2001-08 | 단위 | 색인 텍스트 라벨(`제목:`, `감독:` …)이 `movielab/data/` 밖에 없는지 검사 (TC-NF2005-03과 같은 검사기) | 0건 | 06 | `tests/unit/test_architecture.py` |

> TC-F2001-06은 데이터 팩이 저장소에 없으므로 CI에서는 `skip`된다. 로컬 검증 결과를 검증 문서에 기록한다.

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.1-3 색인 텍스트 1건 | `--show 157336` 출력 저장 (줄거리는 TMDB 원문 재배포를 피하려고 앞부분만) | `docs/verification/evidence/V4.1-3_index_text.txt` |

## 8. 범위 밖

- 메타데이터 보강(포스터, 추가 필드 수집). 색인 자체는 SPEC-F2002.
