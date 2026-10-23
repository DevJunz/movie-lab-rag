# SPEC-F2009 영화 선택 및 질의응답

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2009** 항목 선택 및 질의응답 (UI · 필수) |
| 구분 | MVP |
| 상태 | Done |
| 담당 모듈 | `movielab/ui/streamlit_app.py`, `movielab/services/qa.py`, `movielab/core/types.py`(`AnswerResult`), `movielab/container.py`(`Services.qa`) |
| 선행 SPEC | SPEC-F2008 |
| 관련 ISSUE | #13 |

## 1. 요구사항 원문

> 항목을 선택하고 채팅으로 질문과 답변을 주고받는다.

명세서 3장 세부 조건:
- ◆ 사용자는 목록에서 질문할 항목을 선택할 수 있어야 한다.
- ◆ 선택한 항목별로 대화 기록이 구분되어 유지되어야 한다.

## 2. 도메인 표현 (Movie Lab)

왼쪽 사이드바에서 영화를 고르고, 채팅으로 질문한다. 대화 기록은 영화별로 따로 저장한다.

## 3. 상세 명세

### 3.1 화면 구성 (Streamlit)

```text
┌ 사이드바 ─────────────────────┐  ┌ 본문 ─────────────────────────────────────┐
│ Movie Lab                    │  │ [질문하기] [관람 가이드] [사실 판정] [조건 탐색] │ ← 메뉴 (session_state["page"])
│ 색인: 영화 964편 / 위키 1,234청크 │  │                                           │
│ 영화 선택: [인터스텔라 (2014) ▾] │  │ 인터스텔라 (2014) · 모험, 드라마, SF        │
│ 감독 크리스토퍼 놀란 · 169분     │  │ 💬 대화 기록 (이 영화의 것만)               │
│ TMDB ↗                      │  │ [질문 입력창]                                │
│ ───                          │  │                                           │
│ 출처: TMDB · 한국어 위키백과     │  │                                           │
│ (CC BY-SA 4.0)               │  │                                           │
└──────────────────────────────┘  └───────────────────────────────────────────┘
```

- 영화 선택: `st.selectbox`. 표시 형식 `제목 (연도)` — 동명 영화 구분. 입력해서 걸러 찾을 수 있다. 기본 선택은 없음(선택 전에는 질문 입력창을 비활성화하고 "영화를 먼저 선택하세요" 안내).
- 영화 목록은 `services`가 `movies.json`에서 읽은 목록을 캐시(`st.cache_data`)해 쓴다.
- 메뉴는 `st.tabs`가 아니라 `session_state["page"]`에 묶인 선택 위젯(가로 라디오 등)으로 만든다 — F2011 카드에서 질문하기 화면으로 **코드로 전환**해야 하기 때문.
  이 SPEC은 메뉴 틀과 `질문하기` 화면만 만든다. 다른 메뉴는 그 기능의 SPEC(F2010 · F2011 …)이 화면 표(`PAGES`)에 더한다.
- 사이드바: 색인 건수(`영화 n편 / 위키 n청크`), 선택한 영화의 `제목 (연도)` · 요약 줄 · 메타 링크, 출처 안내(`DomainProfile.attribution_notice`).
  요약 줄은 `DomainProfile.item_caption(item)`(영화: `장르 · 감독 · 상영 시간`)이 만든다 — `ui/`에 도메인 필드 이름을 두지 않는다 (NF2005).
  건수를 못 읽으면(색인 없음) 건수 줄을 생략한다 — 색인 0건 안내는 SPEC-F2012.
- 서비스 객체(LLM, Chroma, 그래프)는 `st.cache_resource`로 한 번만 만든다.
- 화면 코드는 `main(services)` 함수 하나로 시작한다. `streamlit run`으로 실행하면 container의 실제 서비스를, 테스트(`AppTest.from_function`)는
  가짜 서비스를 넘긴다. `services`가 제공하는 것: `catalog`(항목 목록 · 조회), `qa`(`QAService`), `profile`, `settings`, 색인 건수.

### 3.2 대화 기록

- `st.session_state["histories"]: dict[movie_id, list[Message]]`. `Message = {role, content, cited, notices, collect_summary}`.
- 영화를 바꾸면 그 영화의 기록만 보인다. 다시 돌아오면 이전 기록이 그대로 보인다.
- 기록은 브라우저 세션 동안만 유지한다(A-20). 사이드바에 "이 영화 대화 지우기" 버튼을 둔다.
- 답변 생성에 이전 대화를 넣지 않는다(A-08) — 영화 간 대화가 섞일 여지를 없애고, 근거와 답의 대응을 단순하게 유지한다.

### 3.3 질문 처리

질문 제출 → `services.qa.ask(movie_id, question, on_progress)` → 진행 상태 표시(F2012) → 답변 + 근거(F2008)를 기록에 추가.

- 이 SPEC은 처리 중 `st.spinner` 하나만 보인다. 단계별 진행 상태 · 수집 상세는 SPEC-F2012, 오류 안내는 SPEC-NF2004가 더한다.
- 답변 메시지 아래에 근거 목록 컴포넌트(F2008 `render_evidence`, 미리보기 길이 `settings.ui.evidence_preview_chars`)를 그린다.
- `AnswerResult`(01-architecture §4): `answer`, `evidences`(검색된 근거 전체), `cited` · `uncited`(F2008), `not_found`(F2007 `is_not_found`),
  `collect`(`CollectReport`), `notices`, `timings`. 이 SPEC은 `timings`에 `collect` · `total`을 채우고, 단계 분리(`retrieve` · `generate`)는 SPEC-NF2001이 한다.
- `QAService.ask` 순서: 항목 조회(없으면 `ItemNotFoundError`) → `collector.collect(item, question, on_progress)` → `graph.invoke({movie_id, question, task: "qa"})`
  → `select_cited(answer, contexts)`.

```python
# movielab/services/qa.py
class QAService:
    def ask(self, movie_id: str, question: str, on_progress=None) -> AnswerResult: ...
```

## 4. 가정

| ID | 내용 |
|---|---|
| A-08 | 단일 턴 |
| A-20 | 세션 동안만 기록 유지 |

## 5. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2009-01 | 사이드바 목록에서 964편 중 영화를 고를 수 있고, 동명 영화는 연도로 구분된다 | — |
| AC-F2009-02 | 선택한 영화에 대해 채팅으로 질문하면 답변과 근거가 대화에 추가된다 | — |
| AC-F2009-03 | 영화 A에서 대화 후 영화 B로 바꾸면 A의 대화가 보이지 않고, A로 돌아오면 A의 대화가 그대로 있다 | V4.4-1 |
| AC-F2009-04 | 질문은 선택한 영화의 `movie_id`로 처리된다 (B를 선택한 상태의 질문이 A 근거로 답해지지 않는다) | V4.4-1 |
| AC-F2009-05 | 영화를 선택하지 않으면 질문할 수 없고 안내가 보인다 | — |

## 6. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2009-01 | 통합 | `AppTest`: 영화 목록 옵션 | 합성 12편, 동명 2편이 `제목 (연도)`로 구분 | 01 | `tests/integration/test_ui_chat.py` |
| TC-F2009-02 | 통합 | `AppTest`: 영화 선택 후 질문 입력 | 가짜 `QAService.ask`가 해당 `movie_id`로 1회 호출, 답변 메시지 표시 | 02, 04 | 〃 |
| TC-F2009-03 | 통합 | `AppTest`: A에서 질문 → B 선택 → B에서 질문 → A 선택 | 각 화면에 자기 질문만 보임 | 03 | 〃 |
| TC-F2009-04 | 통합 | `AppTest`: 미선택 상태 | 입력창 비활성, 안내 문구 | 05 | 〃 |
| TC-F2009-05 | 단위 | `QAService.ask`: 수집기 · 그래프 가짜로 호출 순서 · 결과 | `collect` → `graph.invoke`, `cited` · `not_found` · `timings` 채움, 없는 영화는 `ItemNotFoundError` | 02 | `tests/unit/test_qa_service.py` |
| TC-F2009-08 | 단위 | `MOVIE_PROFILE.item_caption`: 감독 · 상영 시간이 있는 영화 / 감독이 빈 영화 | `모험, 드라마, SF · 감독 크리스토퍼 놀란 · 169분` / 빈 항목은 빠짐 | 01 | `tests/unit/test_domain_movie.py` |
| TC-F2009-07 | 통합 | `AppTest`: 답변 메시지 아래 근거 목록 · "이 영화 대화 지우기" | 인용 근거만 보임 / 지우면 그 영화 기록만 사라짐 | 02, 03 | `tests/integration/test_ui_chat.py` |
| TC-F2009-06 | 수동 | 인터스텔라 → 명량 → 인터스텔라 전환 (실제 서비스로 `streamlit run`) | 대화가 섞이지 않음 캡처 | 03 | 스크린샷 |

## 7. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.4-1 | 실제 서비스로 화면 함수(`main`)를 `AppTest`로 실행해 인터스텔라 → 명량 → 인터스텔라 전환 전후 대화 기록 (브라우저 캡처는 수동 단계로 추가) | `docs/verification/evidence/V4.4-1_history.txt` |

## 8. 범위 밖

- 대화 기록 영구 저장 · 내보내기.
