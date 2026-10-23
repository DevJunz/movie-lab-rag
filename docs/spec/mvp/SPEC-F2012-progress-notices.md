# SPEC-F2012 진행 상태 및 안내

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2012** 진행 상태 및 안내 (UI · 필수) |
| 구분 | MVP |
| 상태 | Done |
| 담당 모듈 | `movielab/core/messages.py`, `movielab/core/errors.py`, `movielab/services/health.py`, `movielab/ui/streamlit_app.py`, `movielab/data/domain_movie.py`(면책 문구 값) |
| 선행 SPEC | SPEC-F2004, SPEC-F2009 |
| 관련 ISSUE | #14 |

## 1. 요구사항 원문

> 처리 중 상태와 오류 안내, 위험 도메인의 면책 안내를 표시한다.

명세서 3장 세부 조건:
- ◆ 문서 수집과 답변 생성 중 진행 상태를 표시해야 한다.
- ◆ 색인이 없거나 API 키 설정이 누락된 경우 안내를 표시해야 한다.
- ◆ 건강 · 금융처럼 판단이 위험한 도메인은 답변이 전문가 조언을 대신하지 않는다는 안내를 표시해야 한다.

## 2. 도메인 표현 (Movie Lab)

문서 수집 중에는 진행 상태 영역에 단계를 띄우고, 끝나면 수집된 문서 제목을 보여 준다. 색인이 0건이면 색인 스크립트를 실행하라고 안내한다.
영화는 위험 도메인이 아니므로 면책 문구는 표시하지 않는다(A-16). 단, 도메인 설정으로 켜면 표시되는 기능은 구현 · 테스트한다.

## 3. 상세 명세

### 3.1 진행 상태

`st.status`(펼칠 수 있는 상태 상자)를 쓰고, 수집기 콜백(SPEC-F2004 §3.3)과 서비스 단계를 사람이 읽는 문구로 바꾼다.

| 단계 키 | 표시 문구 |
|---|---|
| `cache_hit` | 이미 수집한 질문입니다. 저장된 문서로 답합니다. |
| `extract_queries` | 검색어를 고르는 중… → 완료 후 `검색어: 웜홀, 블랙홀, …` |
| `resolve_item_doc` | 영화 문서를 찾는 중… |
| `search` | 위키백과에서 후보 문서를 찾는 중… (`n/N` 검색어) |
| `filter` | 후보 문서를 정리하는 중… |
| `select` | 읽을 문서를 고르는 중… |
| `fetch` | 문서 본문을 가져오는 중… (`n/N`) |
| `index` | 문서를 색인하는 중… |
| `retrieve` | 근거를 찾는 중… |
| `generate` | 답변을 작성하는 중… |
| `done` | 완료 — 수집한 문서: `인터스텔라`, `블랙홀`, … (버린 문서 n건) |

- `retrieve` · `generate`는 `QAService`가 보낸다: 그래프를 `stream(stream_mode="updates")`로 돌려 `retrieve` 시작 전에 `retrieve`,
  `retrieve` 노드가 끝나면 `generate`를 알린다 (그래프 노드는 두 개 그대로, F2007).
- 단계 문구는 `core/messages.PROGRESS`(단계 키 → 템플릿)에서 가져온다. 모르는 단계 키는 표시하지 않는다.
- 완료되면 상태 상자를 접고 라벨을 `완료 (n.n초)`로 바꾼다. 펼치면 수집 상세(검색어, 색인 / 버림 목록과 사유)를 볼 수 있다 (V4.2-1, V4.2-2 증빙에도 사용).
- 관람 가이드 · 사실 판정 · 조건 탐색에도 같은 방식으로 표시한다.

### 3.2 안내 문구 (`core/messages.py`, 표시 위치)

문구는 템플릿이고 `{item_label}` · `{meta_source_label}` · `{doc_source_label}`을 `DomainProfile` 값으로 채운다(NF2005). 아래 표는 영화 프로필로 채운 결과다.

| 코드 | 상황 | 문구 (영화 프로필 적용) | 동작 |
|---|---|---|---|
| `API_KEY_MISSING` | `GMS_API_KEY` 또는 `GMS_BASE_URL` 없음 | GMS API 키가 설정되지 않았습니다. `.env` 파일에 `GMS_API_KEY`와 `GMS_BASE_URL`을 설정한 뒤 다시 실행하세요. | `st.error` + `st.stop()` (앱 시작 시) |
| `INDEX_EMPTY` | `movie_meta` 0건 | 영화 색인이 비어 있습니다. 터미널에서 `python -m scripts.index_meta`를 실행하세요. | `st.warning`, 질문 · 탐색 비활성 |
| `ITEM_NOT_INDEXED` | 선택 영화의 메타 청크 없음 | 이 영화는 아직 색인되지 않았습니다. `python -m scripts.index_meta`를 다시 실행하세요. | `st.warning` |
| `NO_EXTERNAL_DOCS` | 외부 근거 0개 | 관련 위키백과 문서를 찾지 못했습니다. 영화 메타데이터만으로 답합니다. | 답변 위 `st.info` |
| `SOURCE_FALLBACK` | 위키 API 대신 제공 묶음 사용 | 위키백과에 연결할 수 없어 미리 수집된 문서 묶음을 사용했습니다. | 상태 상자 안 `st.info` |
| `UNCITED` | 인용 0건 | 이 답변에는 인용된 근거가 없습니다. | 근거 목록 자리 `st.info` (F2008) |
| `EXPLORE_EMPTY` | 조건 탐색 결과 0 | 조건에 맞는 영화를 찾지 못했습니다. 조건을 바꿔 보세요. | `st.info` (F2011) |
| `GENERIC_ERROR` | 그 밖의 예외 | 처리 중 문제가 발생했습니다. 잠시 후 다시 시도하세요. | `st.error` (상세는 로그만, NF2004) |
| `DISCLAIMER` | `DomainProfile.disclaimer`가 있고 `domain.disclaimer_enabled == true` | (도메인이 정한 문구) | 모든 답변 · 특화 기능 결과 아래 `st.caption` |

- 시작 점검은 `services.health() -> HealthStatus{api_key_ok, meta_count, docs_count}` 하나로 한다(`services/health.check(settings, store)`).
  사이드바 색인 건수도 이 값을 쓴다 — F2009의 `index_counts()`를 대신한다. 건수는 임베딩(키) 없이 읽는다.
- `NO_EXTERNAL_DOCS`는 `AnswerResult.no_external`(F2006 `RetrievalResult.no_external`을 그래프 상태로 전달)로 판단한다.
- 질문 처리 중 안내 오류(`MovieLabUserError`: `ITEM_NOT_INDEXED` 등)는 그 코드의 문구를, 그 밖의 예외는 `GENERIC_ERROR`를 답변 자리에 `st.error`로 보인다
  (예외 메시지 · traceback은 로그만).
- 키 확인은 **값이 있는지만** 본다. 화면에 키 값 · 일부 · 길이를 표시하지 않는다(NF2004).

### 3.3 면책 안내

- `DomainProfile.disclaimer: str | None`. 영화 프로필은 `None`(A-16).
- 표시 조건: `disclaimer`가 있고 `settings.domain.disclaimer_enabled`가 `true`.
- 테스트에서는 면책 문구가 있는 테스트용 프로필을 주입해 표시를 검증한다.

## 4. 가정

| ID | 내용 |
|---|---|
| A-16 | 영화는 위험 도메인이 아님 → 기본 미표시 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2012-01 | 문서 수집과 답변 생성 중 단계별 진행 상태가 보이고, 완료 후 수집한 문서 제목이 보인다 | V4.4-4 |
| AC-F2012-02 | API 키가 없으면 앱 시작 시 키 안내가 보이고 이후 처리가 멈춘다 | V4.4-5 |
| AC-F2012-03 | 메타 색인이 0건이면 색인 스크립트 실행 안내가 보이고 질문 · 탐색이 비활성화된다 | V4.4-5 |
| AC-F2012-04 | 외부 문서 검색 결과가 없으면 그 사실이 안내된다 | V4.4-5 |
| AC-F2012-05 | 면책 문구가 설정된 도메인이면 결과마다 면책 안내가 보이고, 영화 도메인 기본값에서는 보이지 않는다 | V4.4-6 |
| AC-F2012-06 | 예외가 나도 화면에는 사용자용 문구만 보인다 (NF2004와 연계) | V4.7-4 |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2012-01 | 통합 | `AppTest`: 가짜 서비스가 `on_progress`로 단계를 보냄 | 상태 상자에 단계 문구, 완료 후 문서 제목 | 01 | `tests/integration/test_ui_status.py` |
| TC-F2012-02 | 통합 | `AppTest`: `GMS_API_KEY` 없음 | `API_KEY_MISSING` 문구, 질문 입력창 없음 | 02 | 〃 |
| TC-F2012-03 | 통합 | `AppTest`: 빈 Chroma | `INDEX_EMPTY` 문구, 입력 비활성 | 03 | 〃 |
| TC-F2012-04 | 통합 | `AppTest`: `no_external=True` 결과 | `NO_EXTERNAL_DOCS` 문구 | 04 | 〃 |
| TC-F2012-05 | 통합 | `AppTest`: 면책 문구 있는 테스트 프로필 + `disclaimer_enabled` | 답변 아래 면책 문구 | 05 | 〃 |
| TC-F2012-06 | 통합 | `AppTest`: 영화 프로필 기본값 | 면책 문구 없음 | 05 | 〃 |
| TC-F2012-07 | 단위 | `health.check()`: 키 유무 · 건수 조합 | `HealthStatus` 값 정확 | 02, 03 | `tests/unit/test_health.py` |
| TC-F2012-08 | 통합 | `AppTest`: 서비스가 `RuntimeError("boom sk-test")` | `GENERIC_ERROR`만 보이고 `boom` · `Traceback` 미노출 | 06 | 〃 |
| TC-F2012-10 | 단위 | `QAService.ask`가 진행 콜백으로 보내는 단계 | 수집 단계들 뒤에 `retrieve` → `generate` 순서, `no_external` 전달 | 01, 04 | `tests/unit/test_qa_service.py` |
| TC-F2012-09 | 수동 | 실제 Q1 첫 수집 / `.env` 없이 실행 / 빈 색인으로 실행 | 각 화면 기록 (실제 서비스 `AppTest` 텍스트, 브라우저 캡처는 수동 단계) | 01~03 | `docs/verification/evidence/V4.4-4_5_status.txt` |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.4-4, V4.4-5 | 실제 서비스로 화면 함수를 `AppTest`로 실행: 첫 수집의 단계 기록 · 완료 라벨 · 수집 상세, 키 없음 · 색인 없음 화면 문구 (브라우저 캡처는 수동 단계로 추가) | `docs/verification/evidence/V4.4-4_5_status.txt` |
| V4.4-6 | 해당 없음(영화) — 테스트 결과로 기능만 증빙 | 검증 결과 문서에 "해당 없음(N/A), 기능 테스트 TC-F2012-05 통과"로 기록 |

## 8. 범위 밖

- 진행률 백분율(단계 수 기반 표시만). 알림 · 소리.
