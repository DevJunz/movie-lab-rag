# SPEC-NF2005 모듈 분리 (+ 테스트 · CI 기반)

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2005** 모듈 분리 (확장성) |
| 구분 | MVP (비기능) — **첫 구현 이슈** |
| 상태 | In Progress |
| 담당 모듈 | 패키지 골격 전체, `movielab/container.py`, `tests/conftest.py`, `tests/fakes/`, `tests/unit/test_architecture.py`, `pyproject.toml`, `.github/workflows/ci.yml` |
| 선행 SPEC | 없음 |
| 관련 ISSUE | #1 |

## 1. 요구사항 원문

> 수집, 색인, 검색, 생성, UI의 책임을 분리하고, 도메인에 묶인 부분은 데이터 준비 영역에 모아야 한다.

## 2. 왜 첫 이슈인가

모든 SPEC의 테스트가 이 SPEC이 만드는 골격(패키지 · 가짜 객체 · 네트워크 차단 · CI)을 쓴다.
요구사항과 1:1 대응을 지키기 위해 테스트 · CI 기반은 별도 SPEC을 두지 않고 이 SPEC의 범위에 넣는다.

## 3. 상세 명세

### 3.1 패키지 골격

[01-architecture.md §2](../01-architecture.md#2-모듈-구조-nf2005)의 디렉터리를 만든다. 각 영역의 책임:

| 영역 (명세서 1.2) | 패키지 | 책임 |
|---|---|---|
| 데이터 준비 | `movielab/data/` | 항목 로드 · 색인 텍스트, 외부 문서 소스(API · 묶음 · PDF), 원문 저장, **도메인 프로필** |
| 수집 | `movielab/collect/` | 검색어 추출, 후보 선별, 수집 오케스트레이션, 캐시 |
| Vector Store (색인) | `movielab/index/` | 컬렉션 생성 · 조회, 청킹 · 임베딩 색인 |
| RAG 파이프라인 (검색 · 생성) | `movielab/rag/` | retrieve/generate 그래프, 병합 · 번호, 인용 |
| 서비스 기능 | `movielab/services/` | QA, 특화 기능, 조건 탐색, 상태 점검 |
| UI | `movielab/ui/`, `movielab/api/`, `web/` | 화면, 서버 |

### 3.2 도메인 종속 코드 격리

- `DomainProfile`(자료형, `core/domain.py`)이 도메인에 따라 달라지는 **모든 문구와 규칙**을 담는다.

| 종류 | 필드 (영화 값) | 쓰는 SPEC |
|---|---|---|
| 라벨 | `item_label`("영화"), `meta_source_label`("영화 메타데이터"), `doc_source_label`("위키백과"), `meta_link_label`("TMDB") | F2007, F2008, F2012 |
| 역할 | `expert_role`("영화 큐레이터"), `assistant_role`("영화 지식 도우미") | P1, P3, G1, E1, E2 |
| 텍스트 생성 | `to_index_text(raw)`, `item_card(item)`(P1 · E2에 넣는 항목 요약) | F2001, F2003, F2011 |
| 항목 자체 문서 | `item_doc_queries(item)`, `pick_item_doc(item, candidates)` | F2003, F2004 |
| 조건 탐색 | `explore_filter_spec`(E1의 구조화 필드 설명), `explore_where(parsed) -> dict \| None`(Chroma `where` 변환) | F2011 |
| 고지 | `attribution_notice`(출처 고지 문장), `disclaimer`(None) | NF2007, F2012 |

- 영화 값은 `data/domain_movie.py`의 `MOVIE_PROFILE` 하나에만 있다. `prompts.py` · `core/messages.py`의 문장은 `{item_label}` 같은 자리표시자를 쓰고 프로필 값으로 채운다.
- 금지 단어 검사: `movielab/` 중 `data/` 밖의 `.py` 파일에 `영화`, `movie_id` 외의 영화 고유 필드명(`tmdb`, `director`, `cast`, `overview`, `original_title`)이 **문자열 리터럴로** 나오지 않는다.
  예외: `config.py`의 기본 경로 문자열, 01-architecture가 정한 공통 메타데이터 키 `movie_id`(청크 필터 키).

### 3.3 의존 규칙 검사

`tests/unit/test_architecture.py`가 `movielab/` 아래 모든 파일의 import를 `ast`로 읽어 [01-architecture.md §2.1](../01-architecture.md#21-의존-규칙)의 표를 검사한다. 위반 시 파일과 줄 번호를 보여 주고 실패한다.

### 3.4 테스트 기반

| 구성 | 내용 |
|---|---|
| `tests/fakes/` | `FakeChatModel`, `FakeEmbeddings`, `FakeHttpSession`, `FakeClock`/`fake_sleep` ([01-architecture.md §10.3](../01-architecture.md#103-가짜-객체-testsfakes)) |
| `tests/conftest.py` | 네트워크 차단(live 제외), `tmp_settings`, `movies_small`, `wiki_small`, 환경변수 격리 |
| `tests/fixtures/` | 합성 데이터만 |
| `pyproject.toml` | pytest 마커(`live`), `addopts = "-m 'not live' --strict-markers"`, ruff(`target-version = "py310"`, `line-length = 100`) |
| `requirements-dev.txt` | `pytest`, `ruff` (이 PR에서 버전 고정) |

### 3.5 CI

`.github/workflows/ci.yml` — [01-architecture.md §10.5](../01-architecture.md#105-ci-github-actions-githubworkflowsciyml). 이 PR이 머지된 뒤 `main` 브랜치 보호(CI 통과 필수)를 설정한다.

### 3.6 조립 지점

`movielab/container.py`의 `build_services(settings, *, llm=None, embeddings=None, http=None, profile=None) -> Services`.
인자를 주면 그것을 쓰고, 없으면 실제 구현을 만든다. UI · API · 스크립트 · 테스트 모두 이 함수로 서비스를 얻는다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-13 | pytest, ruff |
| A-14 | CI Python 3.12 + ruff `py310` 문법 검사 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2005-01 | 수집 · 색인 · 검색 · 생성 · UI가 서로 다른 패키지에 있다 | V4.7-5 |
| AC-NF2005-02 | 의존 규칙 위반이 0건이다 (테스트로 매번 검사) | V4.7-5 |
| AC-NF2005-03 | 영화 도메인 고유 문구 · 필드명은 `movielab/data/` 밖에 없다 | V4.7-5 |
| AC-NF2005-04 | 테스트용 `DomainProfile`을 주입하면 `data/` 밖 코드를 바꾸지 않고 다른 도메인 문구로 동작한다 | V4.7-5 |
| AC-NF2005-05 | `live`가 아닌 테스트에서 네트워크 연결을 시도하면 실패한다 | — |
| AC-NF2005-06 | PR마다 CI(린트 + 테스트)가 실행되고, GMS 키 없이 통과한다 | — |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2005-01 | 단위 | 패키지 존재 · 책임별 모듈 존재 | 01-architecture §2 목록과 일치 | 01 | `tests/unit/test_architecture.py` |
| TC-NF2005-02 | 단위 | import 규칙 검사 | 위반 0 | 02 | 〃 |
| TC-NF2005-03 | 단위 | 금지 단어 검사 (`data/` 밖) | 0건 | 03 | 〃 |
| TC-NF2005-04 | 단위 | 규칙 검사기에 위반 예제 코드 입력 | 위반 검출 (검사기 자체 검증) | 02 | 〃 |
| TC-NF2005-05 | 통합 | "도서" 테스트 프로필로 `DomainProfile.render` 문구 생성. **F2003 · F2007 구현 PR에서 P1 · P3 프롬프트 검사를 이 파일에 추가한다** | 문구에 "도서" 역할, "영화" 없음 | 04 | `tests/integration/test_domain_swap.py` |
| TC-NF2005-06 | 단위 | live 마커 없는 테스트에서 `socket.create_connection` (루프백은 허용 — Windows의 `socketpair`가 루프백 연결을 쓴다) | 외부 주소는 예외, 루프백은 통과 | 05 | `tests/unit/test_network_guard.py` |
| TC-NF2005-07 | CI | 이 PR의 Actions 실행 | 린트 · 테스트 통과 | 06 | GitHub Actions |
| TC-NF2005-08 | 단위 | 가짜 객체 동작: `FakeChatModel` 작업 분기 · 기록 · 예외, `FakeEmbeddings` 결정성 · 유사도 순서, `FakeHttpSession` 응답 순서 · 기록, `FakeClock` | 정의대로 동작 | 06 | `tests/unit/test_fakes.py` |
| TC-NF2005-09 | 단위 | `load_settings()` 기본 파일 · `MOVIELAB_SETTINGS` 지정 파일 · `tmp_settings` 픽스처 | 값 · 경로가 정확, 임시 경로는 `tmp_path` 아래 | 06 | `tests/unit/test_config.py` |
| TC-NF2005-10 | 단위 | `build_services(..., llm=가짜, embeddings=가짜, profile=도서)` | 주입한 객체를 그대로 담는다 | 04 | `tests/unit/test_container.py` |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-5 | 디렉터리 트리 + 의존 규칙 테스트 결과 | 설계문서 · 검증 결과 문서 |

## 8. 범위 밖

- 플러그인 방식의 도메인 동적 로딩.
