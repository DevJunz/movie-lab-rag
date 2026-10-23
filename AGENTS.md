# AGENTS.md — Movie Lab 작업 규칙

이 저장소에서 일하는 모든 에이전트(Claude Code 등)와 사람이 따르는 규칙이다.
**SPEC Driven + Test Driven**: SPEC이 먼저, 테스트가 다음, 코드는 마지막이다.

---

## 1. 프로젝트 한눈에

- **Movie Lab**: 영화를 고르고 질문하면 영화 메타데이터(`movies.json`, 964편)와 한국어 위키백과 문서에서 근거를 찾아 `[근거 n]`과 원문 출처를 붙여 답하는 RAG 서비스.
- 스택: Python 3.10+, Streamlit, ChromaDB, LangChain, LangGraph, SSAFY GMS(OpenAI 호환). 버전은 [01-architecture.md §1](docs/spec/01-architecture.md#1-기술-스택과-고정-버전-명세서-12)에 고정.
- 문서 지도:

| 알고 싶은 것 | 문서 |
|---|---|
| 무엇을 왜 만드나, 결정 사항 · 가정 | [docs/spec/00-product-overview.md](docs/spec/00-product-overview.md) |
| 구조 · 데이터 · 설정 · 프롬프트 · 테스트 전략 | [docs/spec/01-architecture.md](docs/spec/01-architecture.md) |
| 요구사항 ↔ SPEC ↔ 테스트, 구현 순서 | [docs/spec/02-traceability.md](docs/spec/02-traceability.md) |
| 제출물 만드는 법 | [docs/spec/03-deliverables.md](docs/spec/03-deliverables.md) |
| 개별 기능 명세 | `docs/spec/mvp/`, `docs/spec/advanced/`, `docs/spec/extensions/` |
| 개발 중 겪은 문제와 해결 | [docs/dev-log.md](docs/dev-log.md) |

## 2. 절대 규칙

1. **SPEC 없이 코드를 쓰지 않는다.** 새 기능 · 동작 변경은 SPEC을 먼저 쓰거나 고친다. 버그 수정도 SPEC의 AC와 어긋난 것이면 그 AC를 근거로, AC가 없던 동작이면 AC를 먼저 추가한다.
2. **필수 기능(F2001~F2012)의 요구 내용은 바꾸지 않는다.** 표현만 영화 도메인에 맞게 바꿀 수 있다. 명세서 원문은 각 SPEC §1에 있다.
3. **라이브러리 버전을 바꾸지 않는다.** `requirements.txt`는 명세서 1.2의 고정 버전 그대로다. 새 의존성은 SPEC에 근거를 쓰고 추가한다.
4. **비밀 값은 `.env`에만 둔다.** 코드 · 문서 · 테스트 · 커밋 메시지 · PR 본문에 키를 쓰지 않는다. `.env`를 커밋하지 않는다.
5. **커밋하면 안 되는 파일**: `.env`, `data/`, `logs/`, `reports/`, `영화도메인_데이터_배포용/`(데이터 팩), `prd.pdf` · `rag_project_briefing.html`(**대외비**). 공개 저장소다.
6. **CI 테스트는 외부를 호출하지 않는다.** 실제 GMS · 위키백과를 부르는 테스트는 `@pytest.mark.live`로만 쓴다.
7. **영화 도메인에 묶인 코드는 `movielab/data/`에만 둔다.** 다른 패키지는 `DomainProfile`을 주입받는다 (SPEC-NF2005).
8. **임의로 정한 값은 "가정"으로 표시한다.** `00-product-overview.md` §8에 `A-xx`로 등록하고 SPEC에서 참조한다. 사용자에게 확인받은 것은 `D-xx`.
9. **모든 문서는 한국어로 쓴다.** 코드 식별자는 영어, 주석 · docstring은 한국어 가능.

## 3. 작업 흐름

```text
① ISSUE ─ ② 브랜치 + SPEC 커밋 ─ ③ TEST(빨강) ─ ④ 코드(초록) ─ ⑤ PR
   ─ ⑥ CI 자동 테스트 ─ ⑦ 리뷰 에이전트 리뷰 ─ ⑧ 머지 ─ ⑨ ISSUE 닫기
```

한 이슈 = 한 SPEC = 한 브랜치 = 한 PR. 구현 순서는 [02-traceability.md §1.1](docs/spec/02-traceability.md#11-구현-순서의-이유)을 따른다.

### ① ISSUE

- SPEC이 없거나 바뀌어야 하면 **먼저 SPEC을 쓴다**(`docs/spec/_template.md`). 확장 기능은 `docs/spec/extensions/` 규칙을 따른다.
- 이슈 생성 (템플릿 `.github/ISSUE_TEMPLATE/spec.md`):

```bash
gh issue create --title "[SPEC-F2001] 영화 메타데이터 적재" --label "spec,mvp" \
  --body "SPEC: docs/spec/mvp/SPEC-F2001-movie-metadata-load.md ..."
```

- 라벨: `spec` + 구분(`mvp` / `advanced` / `extension`). 선행 이슈가 있으면 본문에 적는다.

### ② 브랜치 생성 후 SPEC 커밋

```bash
git switch main && git pull
git switch -c feat/F2001-movie-metadata-load
```

- 브랜치 이름: `feat/<요구사항번호>-<영문-슬러그>` (확장 `feat/X001-...`, 문서만 `docs/...`, 수정 `fix/<번호>-...`).
- **첫 커밋은 SPEC 커밋이다.** SPEC 상태를 `In Progress`로, "관련 ISSUE"에 이슈 번호를 채우고, 구현 전에 알게 된 보완 사항을 반영한다.
  새 SPEC이면 SPEC 파일 추가가 이 커밋이다. `02-traceability.md`의 상태 · 이슈 열도 함께 고친다.

```bash
git commit -m "docs(spec): SPEC-F2001 착수 (#12)"
```

### ③ TEST 작성 (빨강)

- SPEC §6 테스트 케이스를 그대로 테스트로 옮긴다. 테스트 이름에 TC ID를 넣는다: `test_tc_f2001_02_empty_director()`.
- 수동(M) TC는 코드로 쓰지 않고 PR의 증빙 항목에 남긴다. live TC는 `tests/live/`에 `@pytest.mark.live`로 쓴다.
- 실행해서 **실패하는 것을 확인**하고 커밋한다(구현이 없어 생기는 import 실패도 빨강으로 인정).

```bash
pytest tests/unit/test_movies.py   # 실패 확인
git commit -m "test(F2001): TC-F2001-01~06 추가 (#12)"
```

### ④ 코드 작업 (초록)

- 테스트를 통과시키는 최소 구현 → 리팩터링. 커밋을 작게 나눈다.
- 로컬 확인 (PR 전에 반드시):

```bash
ruff check . && ruff format --check . && pytest
```

- SPEC과 다르게 구현해야 할 이유가 생기면 **코드를 SPEC에 맞추지 말고 멈춘다.** SPEC을 고치는 커밋을 먼저 하고(사용자 확인이 필요한 변경이면 확인을 받고) 진행한다.
- 개발 중 겪은 문제와 해결은 `docs/dev-log.md`에 한 항목씩 남긴다(설계문서 "겪은 문제, 해결 과정"의 원본).

```bash
git commit -m "feat(F2001): movies.json 로드와 색인 텍스트 구성 (#12)"
```

### ⑤ PR

```bash
git push -u origin feat/F2001-movie-metadata-load
gh pr create --base main --title "[SPEC-F2001] 영화 메타데이터 적재" --body-file <작성한 본문>
```

- 본문은 `.github/pull_request_template.md` 양식: SPEC 링크, `Closes #이슈`, AC 체크리스트(AC ↔ TC), 테스트 결과, live 실행 여부, 수동 증빙, 가정 변경, 문제와 해결.
- PR에 SPEC 상태 `Done`, 02-traceability 상태 `Done` 변경을 포함한다(머지되면 그대로 반영).

### ⑥ CI 테스트 자동화

- GitHub Actions(`.github/workflows/ci.yml`)가 PR마다 `ruff` + `pytest -m "not live"`를 돌린다. 키 없이 통과해야 한다.
- 결과 확인: `gh pr checks <PR번호> --watch`. 실패하면 고쳐서 다시 푸시한다. **CI가 초록이 되기 전에는 리뷰를 요청하지 않는다.**

### ⑦ 리뷰 에이전트 리뷰

- CI 통과 후, **구현한 세션과 다른 새 Claude Code 세션**에서 실행한다 (구현 맥락에 끌려가지 않는 독립 리뷰):

```text
/code-review <PR번호> --comment
```

- 리뷰는 §7 체크리스트를 기준으로 본다. 지적 사항은 고치는 커밋을 올리고(⑥ CI 다시 통과), 코드가 크게 바뀌었으면 ⑦을 다시 한다.
- 고치지 않기로 한 지적은 PR 코멘트에 이유를 남긴다.

### ⑧ 머지

- 조건: CI 초록 + 리뷰 지적 해결(또는 사유 기록) + PR 체크리스트 완료.

```bash
gh pr merge <PR번호> --squash --delete-branch
```

### ⑨ ISSUE 닫기

- PR 본문의 `Closes #이슈`로 자동으로 닫힌다. `gh issue view <이슈번호>`로 닫혔는지 확인한다. 안 닫혔으면 `gh issue close <이슈번호> --comment "PR #<번호>로 완료"`.
- `main`에서 `02-traceability.md` 상태가 `Done`인지 확인한다.

### 부트스트랩 (최초 1회)

1. GitHub 공개 저장소 `movie-lab-rag` 생성(A-01), 첫 커밋 = 이 문서와 `docs/spec/` 전체 + `.gitignore` (`main`에 직접, 유일한 예외).
2. 라벨 생성: `spec`, `mvp`, `advanced`, `extension`.
3. SPEC 23개에 대한 이슈를 구현 순서대로 만든다.
4. 첫 구현 이슈는 **SPEC-NF2005**(패키지 골격 · 테스트 기반 · CI). 이 PR이 머지되면 `main` 브랜치 보호(CI 통과 필수, 직접 푸시 금지)를 켠다.

## 4. 커밋 · 브랜치 · PR 규칙

- 커밋 메시지: `<종류>(<요구사항번호>): <한국어 설명> (#이슈)`. 종류 `docs` · `test` · `feat` · `fix` · `refactor` · `chore` · `ci`.
- PR 하나에 SPEC 하나. 관련 없는 수정을 섞지 않는다. 리뷰하기 쉽게 변경을 작게 유지한다.
- `main`에 직접 커밋하지 않는다(부트스트랩 제외). 강제 푸시는 자기 기능 브랜치에서만.

## 5. SPEC 작성 규칙

- 템플릿 `docs/spec/_template.md`의 절을 모두 채운다: 요구사항 원문, 도메인 표현, 상세 명세, 가정, 인수 조건, 테스트 케이스, 증빙, 범위 밖.
- MVP SPEC은 명세서 요구사항과 **1:1**이다. SPEC을 합치거나 쪼개지 않는다. 공통 내용은 `01-architecture.md`에 둔다.
- 명세서 4장의 검증 항목은 해당 SPEC의 **AC와 TC로** 옮기고, AC 표에 `V4.x-y`를 적는다.
- AC 하나에 TC가 하나 이상 있어야 한다. 자동화할 수 없는 것은 수동(M) TC + 증빙 경로.
- 공통 문서(00~03)를 바꾸면 영향받는 SPEC도 같은 PR에서 고친다.

## 6. 코드와 테스트 규칙

**구조**
- 의존 방향은 [01-architecture.md §2.1](docs/spec/01-architecture.md#21-의존-규칙)의 표대로다. `tests/unit/test_architecture.py`가 검사한다.
- 구체 구현은 `movielab/container.py`에서만 조립한다. LLM · 임베딩 · HTTP 세션 · `sleep` · 시계 · 설정 경로는 생성자로 주입받는다.
- 조정 가능한 숫자(청크 크기, Top-k, 호출 간격 …)는 `config/settings.json`에서만 읽는다. 코드에 하드코딩하지 않는다.
- 사용자에게 보이는 문구는 `movielab/core/messages.py`에서만 가져온다. 예외 메시지 · traceback을 화면에 내보내지 않는다(NF2004).
- Python 3.10 호환: `tomllib`, `typing.Self`, `ExceptionGroup`, `except*`를 쓰지 않는다.

**테스트**
- 가짜 객체는 `tests/fakes/`의 것을 쓴다(`FakeChatModel`, `FakeEmbeddings`, `FakeHttpSession`, `FakeClock`). 테스트마다 새로 흉내 내지 않는다.
- live가 아닌 테스트는 네트워크가 막혀 있다(`conftest.py`). 막혀서 실패하면 주입을 빠뜨린 것이다.
- 픽스처는 합성 데이터만. 위키백과 원문을 복사하지 않는다(NF2007).
- Chroma는 `tmp_path`의 새 `PersistentClient`를 쓴다.
- 결정적이어야 한다: 시간 · 무작위 · 순서에 기대는 테스트를 쓰지 않는다.
- live 테스트는 해당 SPEC에 live TC가 있으면 PR 전에 로컬에서 `pytest -m live -k <TC>`로 돌리고 결과를 PR에 적는다(키가 없으면 "미실행"으로 적는다).

## 7. 리뷰 체크리스트 (리뷰 에이전트 · 사람 공통)

- [ ] PR이 SPEC 하나에 대응하고, SPEC의 모든 AC가 충족되었다(PR 체크리스트와 테스트로 확인).
- [ ] SPEC §6의 자동 TC가 모두 테스트로 있고 TC ID가 이름에 있다.
- [ ] SPEC에 없는 동작을 추가하지 않았다. 있다면 SPEC이 먼저 바뀌었다.
- [ ] 의존 규칙 위반, `data/` 밖의 영화 도메인 코드가 없다.
- [ ] 설정값 하드코딩, 비밀 값, 대외비 파일이 없다.
- [ ] 화면 · API 응답에 traceback · 키 · 프롬프트 전문이 나가지 않는다.
- [ ] 외부 호출은 주입 가능하고, CI 테스트가 외부를 부르지 않는다.
- [ ] 위키 근거에 출처 · 라이선스가 유지된다.
- [ ] 정확성 버그: 청크 ID에 `movie_id` 포함, `page_id` 문자열 정규화, 근거 번호와 인용 목록 일치, 캐시 기록 시점.
- [ ] 문서(SPEC 상태, 02-traceability, dev-log)가 갱신되었다.

## 8. 자주 쓰는 명령

```bash
pip install -r requirements.txt -r requirements-dev.txt     # 설치
ruff check . && ruff format --check . && pytest              # CI와 같은 검사
pytest -m live                                               # 실제 API 테스트 (.env 필요)
python -m scripts.index_meta                                 # 영화 메타 색인
python -m scripts.collect --movie-id 157336 --question "…"   # 수집 + 색인
streamlit run movielab/ui/streamlit_app.py                   # 앱 실행
gh pr checks <PR번호> --watch                                 # CI 확인
```
