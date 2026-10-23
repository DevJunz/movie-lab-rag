# SPEC-NF2002 수집 캐시

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2002** 수집 캐시 (성능) |
| 구분 | MVP (비기능) |
| 상태 | Done |
| 담당 모듈 | `movielab/collect/manifest.py`, `movielab/collect/collector.py` |
| 선행 SPEC | SPEC-F2004 |
| 관련 ISSUE | #8, #33 |

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
- **색인 확인**: 수집을 시작할 때 매니페스트에 **색인했다고 기록된 문서(`page_ids`)** 가운데 **실제 색인(`wiki_docs`)에 청크가 없는 문서가 하나라도 있으면**
  (`data/chroma`를 지움, 일부 문서 청크만 사라짐, 이전에 초기화가 실패해 옛 기록이 남음 등) 질문 캐시 적중 여부와 상관없이 그 영화의 매니페스트를 비우고 새로 수집한다.
  매니페스트는 색인의 '힌트'일 뿐이고, 믿기 전에 매번 색인과 대조한다(영화당 메타데이터 조회 한 번).
  색인한 문서가 하나도 없던 영화(검색 결과에서 고른 문서가 없음)는 청크가 0개인 것이 정상이므로 캐시를 비우지 않는다.
- 캐시는 영화별이다. 영화 A에서 검색한 「크리스토퍼 놀란」은 영화 B에서 다시 검색될 수 있다(청크 ID가 영화별이기 때문, F2005).

### 3.3 저장 안전성

- 매니페스트는 여러 인스턴스 · 프로세스(앱과 `--reset-cache` 스크립트 등)가 함께 쓴다 (#33).
  - **파일을 바꾸는 일(기록 · 초기화 · 깨진 파일 백업)은 OS 파일 잠금 안에서 한다**: `manifest.json.lock`을 열어
    Windows는 `msvcrt.locking`, 그 밖은 `fcntl.flock`으로 배타 잠금을 잡는다. 잠금은 프로세스가 죽으면 OS가 풀어 주므로
    '오래된 잠금' 판단 · 잠금 파일 삭제가 없다 (잠금 파일은 지우지 않고 남겨 둔다).
  - 잠금 안에서는 서명과 상관없이 파일을 **항상 다시 읽은 뒤** 고쳐 쓴다 — 다른 인스턴스 · 프로세스의 기록을 덮어쓰지 않는다.
  - 잠금은 `settings.cache.lock_poll_sec` 간격으로 최대 `lock_timeout_sec` 기다린다(A-24). 기다리는 것은 **다른 쪽이 잠금을 쥐고 있을 때**
    (`EACCES` · `EAGAIN` · `EWOULDBLOCK` · `EDEADLK`)뿐이다. 잠금 파일을 열 수 없거나 파일 시스템이 잠금을 지원하지 않으면(`ENOLCK` 등)
    기다리지 않고 바로 포기한다. 포기하면 경고 로그를 남기고 이번 기록을 건너뛴다 (캐시는 성능용이라 수집을 실패시키지 않는다).
  - **수집기는 수집 한 번의 결과를 끝에서 한 번에 기록한다**: `record_collection(item_id, pages, item_doc_page_id, keywords, question)`.
    잠금 한 번 · 쓰기 한 번이고, 전부 기록되거나 하나도 기록되지 않는다 — 문서는 기록됐는데 검색어 · 질문만 빠지거나,
    문서만 기록되고 항목 자체 문서 표시가 빠지는 상태가 생기지 않는다. 검색어 · 질문은 §3.2 규칙(완전히 성공)일 때만 넣는다.
    수집 도중 프로세스가 끝나거나 예외로 수집이 중단되면 그 수집은 기록되지 않는다 — 다음 질문에서 다시 받을 뿐이다
    (부분 기록보다 '전부 또는 없음'을 택했다: 부분 기록은 문서 · 검색어 · 질문 사이의 불일치를 만든다).
    기록할 것(문서 · 검색어 · 질문)이 하나도 없으면 파일을 쓰지 않는다 (빈 항목을 만들지 않는다).
  - `record_*` · `record_collection` · `reset()`은 기록에 성공했는지 돌려준다. 기록 함수 안의 예외(내용 변경 중 오류)도 수집을 실패시키지 않는다:
    경고 로그를 남기고 메모리를 무효로 표시한 뒤 `False`.
  - `reset()`은 초기화에 성공했는지 돌려준다. `--reset-cache`가 실패하면 성공 문구 대신 `CACHE_RESET_FAILED`를 출력하고 종료 코드 1.
    수집기의 색인 확인(§3.2)에서 초기화가 실패하면 이번 수집은 매니페스트를 읽지도 쓰지도 않고(`NullManifest`) 새로 수집한다.
    잠금을 기다리는 동안 인스턴스 안의 조회는 막지 않는다 (스레드 잠금은 파일 잠금을 잡은 뒤에만 쥔다).
  - 조회는 잠금 없이, 파일 서명 `(st_ino, st_mtime_ns, st_size)`가 바뀌었을 때만 다시 읽는다. 수정 시각만 보면 같은 타이머 틱
    안의 두 쓰기를 놓친다(Windows는 파일 시각이 수 ms 단위로만 바뀐다). 쓰기는 늘 새 임시 파일을 바꿔 넣어 파일 ID가 달라진다.
    자기 쓰기의 서명은 바꿔 넣기 **전에** 임시 파일에서 얻는다. 기록 손실은 잠금 안의 재읽기가 막으므로, 서명이 드물게 겹쳐도
    조회가 잠깐 옛 내용을 보는 정도에 그친다.
  - 조회 중 깨진 파일(JSON 해석 실패 · UTF-8이 아님 · 구조 오류)을 만나면 메모리는 빈 매니페스트로 두고, 잠금을 **기다리지 않고** 한 번 잡아 보아
    잡히면 다시 읽어도 깨져 있을 때만 백업한다 (그 사이 다른 프로세스가 정상 파일을 쓴 경우 그 파일을 옮기지 않는다). 백업하려는 사이 파일이 사라졌으면 넘어간다.
    같은 서명의 파일에는 다시 시도하지 않는다 (조회마다 재시도 · 잠금 비용을 치르지 않는다). 기록할 때는 잠금 안에서 다시 확인해 백업한다.
  - 백업(바꿔 넣기)이 실패하면 깨진 파일을 덮어쓰지 않도록 이번 기록을 건너뛴다.
  - 일시적인 읽기 오류(`OSError` — Windows 공유 위반 등)는 파일 손상으로 보지 않는다(백업하지 않는다): `io_retries`번 다시 시도하고(A-24),
    그래도 안 되면 **메모리를 빈 매니페스트로 둔다**(옛 내용을 새 서명과 짝지어 믿지 않는다 — 다른 프로세스의 초기화를 놓치지 않게).
    캐시를 못 쓰면 다시 수집할 뿐 결과는 틀리지 않는다. 기록 중이면 그 기록을 건너뛴다. 이 서명의 파일은 바뀔 때까지 다시 읽지 않는다.
  - 파일 정보(`stat`)를 읽지 못하는 오류(`PermissionError` 등)도 수집을 실패시키지 않는다. 이때 서명은 '알 수 없음'이며
    '파일 없음'과 구분한다 — 알 수 없으면 조회할 때마다 다시 읽는다 (다른 프로세스의 초기화를 놓치지 않게).
  - 쓰기 · 바꿔 넣기에서 `PermissionError`(다른 프로세스가 읽는 중)는 몇 번 다시 시도하고, 그 밖의 `OSError`(디스크 가득 등)나 끝내 실패하면
    임시 파일을 지우고 경고 로그만 남긴다. 이때 메모리 내용을 무효로 표시해 다음 조회가 파일에서 다시 읽는다 (저장되지 않은 기록이 캐시 적중으로 보이지 않게).
  - 잠금 · 재시도 수치는 `settings.cache`(`lock_timeout_sec`, `lock_poll_sec`, `io_retries`, `io_retry_wait_sec`)에서 container가 넘긴다.
    생성자에 기본값을 두지 않는다. 시각(`clock`) · 대기(`sleep`)는 생성자로 주입하고, 테스트는 `FakeClock`을 쓴다.
  - 조회 서명은 리눅스에서 파일 ID가 곧바로 재사용되면 드물게 겹칠 수 있다. 기록은 잠금 안에서 항상 다시 읽으므로 손실은 없고,
    조회가 다음 변경 전까지 옛 내용을 볼 수 있는 정도이다 (캐시 판단용이라 허용).
- 구조가 틀린 내용(최상위가 객체가 아님, 항목 값이 객체가 아님, 목록 필드가 목록이 아님, `chunks`가 정수가 아님,
  `item_doc_page_id` · `collected_at`이 문자열 · null이 아님)도 깨진 파일과 같게 처리한다(백업 후 새로 시작).
- 백업(`os.replace`)도 쓰기와 같이 `PermissionError`면 `io_retries`번 다시 시도한다.
- 서명을 알 수 없을 때(stat 실패) 조회마다 다시 읽되, 이때는 재시도 · 대기 없이 한 번만 읽는다(조회 비용 상한).
- 날짜(`collected_at`) · 백업 시각은 주입된 함수로 정한다. 백업 파일 이름은 겹치지 않게 만든다.

- 쓰기는 임시 파일에 쓴 뒤 `os.replace`로 바꾼다(중간에 끊겨도 깨진 JSON이 남지 않음).
- 파일이 없으면 빈 매니페스트로 시작한다. JSON이 깨져 있으면 `manifest.json.broken-<시각>`으로 옮겨 두고 빈 매니페스트로 시작하며 경고 로그를 남긴다.
- 캐시를 지우는 명령: `python -m scripts.collect --reset-cache [--movie-id ID]` (LLM · 키 없이 동작, `Services.manifest`).
- 매니페스트와 Chroma가 어긋나는 경우(사용자가 `data/chroma`만 지운 경우)를 위해 `scripts.collect --reset-cache [--movie-id]`로 캐시를 지울 수 있다.
  또한 질문 캐시 적중이지만 `wiki_docs`에 그 영화 청크가 0개면 캐시를 믿지 않고 다시 수집한다. 대조는 `Collector`에 주입한 `indexed_pages(item_id) -> set[page_id]`(그 영화의 색인에 청크가 있는 문서)로 한다
  (색인기는 F2005에서 연결 — 주입되지 않으면 이 확인을 건너뛴다).
- 매니페스트 형식에 `item_doc_page_id`(항목 자체 문서의 page_id)를 더한다.
- 질문 캐시 적중으로 수집 전체를 생략하면 `CollectReport.notices`에 `CACHE_HIT`를 남기고 `source_used = "cache"`(01-architecture §4.4의 값 목록에 추가), 진행 상태 `cache_hit` → `done`만 보낸다.

### 3.4 인터페이스

```python
class Manifest:
    def __init__(self, path: Path, *, lock_timeout_sec, lock_poll_sec, io_retries, io_retry_wait_sec,
                 today=date.today, now=datetime.now, clock=time.monotonic, sleep=time.sleep): ...
    # 조회
    def cached_queries(self, movie_id, question) -> list[str] | None: ...
    def has_keyword(self, movie_id, query) -> bool: ...
    def has_page(self, movie_id, page_id) -> bool: ...
    def has_any(self, movie_id) -> bool: ...
    def item_doc_page_id(self, movie_id) -> str | None: ...
    # 기록 — 모두 성공 여부를 돌려준다. 수집기는 record_collection만 쓴다
    def record_collection(self, movie_id, *, pages=(), item_doc_page_id=None, keywords=(), question=None) -> bool: ...
    def record_question(self, movie_id, question, queries) -> bool: ...      # 아래 넷은 record_collection의 얇은 래퍼
    def record_keyword(self, movie_id, query) -> bool: ...
    def record_item_doc(self, movie_id, page_id) -> bool: ...
    def record_page(self, movie_id, page_id, title, chunks, rejected=False) -> bool: ...
    def reset(self, movie_id=None) -> bool: ...

class FileLock:  # OS 파일 잠금 (§3.3)
    def __init__(self, path, *, poll_sec, clock=time.monotonic, sleep=time.sleep): ...
    def acquire(self, timeout_sec=0.0) -> bool: ...
    def release(self) -> None: ...
```

## 4. 가정

| ID | 내용 |
|---|---|
| A-24 | 매니페스트 잠금 · 재시도 수치 (`settings.cache`) |

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
| AC-NF2002-08 | 여러 인스턴스가 동시에 기록해도 기록이 사라지지 않고, 일시적인 파일 오류가 멀쩡한 매니페스트를 백업으로 옮기거나 수집을 실패시키지 않는다 | — |

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
| TC-NF2002-15 | 단위 | 다른 인스턴스가 **같은 크기**의 내용을 새 파일로 바꿔 넣고 수정 시각을 이전 값으로 되돌림 (파일 ID만 다름) | 다시 읽어 바뀐 내용을 본다 | 06 | `tests/unit/test_manifest_safety.py` |
| TC-NF2002-16 | 단위 | 스레드 2개가 각자의 `Manifest` 인스턴스로 서로 다른 검색어를 번갈아 많이 기록 | 기록이 하나도 사라지지 않음, 임시 파일이 남지 않음 | 08 | 〃 |
| TC-NF2002-17 | 단위 | 잠금 파일만 남아 있음(잡은 쪽 없음) / 다른 핸들이 잠금을 쥐고 있음(가짜 시계) / 쥔 쪽이 놓음 | 바로 기록 / 예외 없이 기록 건너뜀 · 경고, 대기 중에도 조회는 막히지 않음 / 다음 기록 성공 | 08 | 〃 |
| TC-NF2002-18 | 단위 | 읽기가 `PermissionError` 한 번 / 계속 · `os.replace`가 `PermissionError` 계속 · 임시 파일 쓰기가 `OSError`(디스크 가득) | 다시 읽어 정상 / 백업 없이 캐시 없이 동작(옛 내용 불신) · 남의 기록 보존 · 예외 없이 임시 파일 정리, 저장 안 된 기록으로 적중 없음 | 05, 08 | 〃 |
| TC-NF2002-20 | 단위 | 잠금을 못 잡는 상태에서 `reset` / `--reset-cache` / 수집기 색인 확인 | `False` / `CACHE_RESET_FAILED` · 종료 코드 1 / 캐시 적중 없이 새로 수집 | 08 | `tests/unit/test_manifest_safety.py`, `tests/integration/test_cache_rules.py` |
| TC-NF2002-21 | 단위 | 잠금이 `ENOLCK`로 실패 / 백업 `os.replace` 실패 / 같은 깨진 파일 · 읽기 실패 파일 반복 조회 | 기다리지 않고 포기 / 깨진 파일을 덮어쓰지 않음 / 두 번째 조회부터 재시도 · 잠금 시도 없음 | 05, 08 | `tests/unit/test_manifest_safety.py` |
| TC-NF2002-22 | 단위 | `cache` 설정 값 검증: `lock_poll_sec: 0`, `io_retries: -1`, `lock_timeout_sec: "10"` | `SettingsError` | 08 | `tests/unit/test_config.py` |
| TC-NF2002-23 | 단위 | `stat`이 `PermissionError` / 읽기가 계속 실패하는 동안 다른 인스턴스가 초기화 / 쓰기 실패 후 다시 읽기도 실패 | 예외 없음 / 옛 기록으로 캐시 적중하지 않음 / 저장 안 된 기록으로 적중하지 않음 | 05, 08 | `tests/unit/test_manifest_safety.py` |
| TC-NF2002-24 | 통합 | 수집 끝의 기록이 실패(잠금을 못 잡음) | 문서 · 검색어 · 질문 · 항목 자체 문서 모두 기록 안 됨 | 01, 04 | `tests/integration/test_cache_rules.py` |
| TC-NF2002-25 | 단위 | 기록 함수 안에서 예외 / `stat`이 계속 실패하는 동안 다른 인스턴스가 초기화 | `False` · 예외 없음 · 다음 조회는 파일에서 / 초기화를 본다 | 05, 08 | `tests/unit/test_manifest_safety.py` |
| TC-NF2002-26 | 통합 | 문서 2건 · 검색어 2개를 수집 | 매니페스트 파일 쓰기 1번, 항목 자체 문서 표시 포함 | 01 | `tests/integration/test_cache_rules.py` |
| TC-NF2002-27 | 단위 | 기록할 것이 없는 `record_collection` / `chunks: "x"`인 파일 / 백업이 `PermissionError` 한 번 | 파일을 만들지 않음 · `has_any` 거짓 / 백업 후 새로 시작 / 다시 시도해 백업 성공 | 05 | `tests/unit/test_manifest_safety.py` |
| TC-NF2002-19 | 단위 | UTF-8이 아닌 매니페스트 / 조회가 깨짐을 본 뒤 잠금 전에 다른 프로세스가 정상 파일을 씀 | 예외 없이 백업 후 새로 시작 / 정상 파일은 옮기지 않음 | 05 | 〃 |
| TC-NF2002-10 | 수동 | Q1을 두 번 질문 | 두 번째에 "이미 수집한 질문입니다" 상태와 짧은 처리 시간 캡처 | 01 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.2-3, V4.7-2 | 같은 질문 2회 실제 실행 결과 — 색인기(F2005) 연결 후 다시 생성: 1회차 30초 수집 · 색인, 2회차 CACHE_HIT · 외부 호출 0 — 화면의 진행 상태 캡처는 F2012 이후 | `docs/verification/evidence/V4.2-3_cache.txt` |

## 8. 범위 밖

- 캐시 만료(TTL). 문서 개정 감지.
