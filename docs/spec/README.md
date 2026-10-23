# Movie Lab SPEC

Movie Lab의 모든 구현은 이 폴더의 SPEC에서 출발한다. 작업 흐름과 규칙은 저장소 루트의 [AGENTS.md](../../AGENTS.md)를 따른다.

## 읽는 순서

1. [00-product-overview.md](00-product-overview.md) — 무엇을 왜 만드나, 도메인 확정, **의사결정(D-xx)** 과 **가정(A-xx)**
2. [01-architecture.md](01-architecture.md) — 모듈 구조, 데이터 모델, 컬렉션 · 청크 ID, 설정, 프롬프트 계약, 테스트 · CI
3. [02-traceability.md](02-traceability.md) — 요구사항 대조표, 명세서 4장 검증 항목 ↔ AC ↔ 테스트
4. [03-deliverables.md](03-deliverables.md) — 명세서 6장 제출물과 SPEC의 연결
5. 개별 SPEC — 구현할 이슈의 SPEC

## SPEC 목록

### MVP — 필수 기능 (명세서 F2001~F2012)

| SPEC | 이름 |
|---|---|
| [SPEC-F2001](mvp/SPEC-F2001-movie-metadata-load.md) | 영화 메타데이터 적재 |
| [SPEC-F2002](mvp/SPEC-F2002-metadata-index.md) | 영화 메타데이터 색인 (RAG 1) |
| [SPEC-F2003](mvp/SPEC-F2003-query-extraction.md) | 검색어 추출 (프롬프트 1) |
| [SPEC-F2004](mvp/SPEC-F2004-document-collection.md) | 위키백과 문서 수집 (프롬프트 2) |
| [SPEC-F2005](mvp/SPEC-F2005-document-index.md) | 위키백과 문서 색인 (RAG 2) |
| [SPEC-F2006](mvp/SPEC-F2006-retrieve-merge.md) | 근거 검색 및 병합 |
| [SPEC-F2007](mvp/SPEC-F2007-grounded-generation.md) | 근거 기반 답변 생성 (프롬프트 3) |
| [SPEC-F2008](mvp/SPEC-F2008-evidence-display.md) | 근거 표시 |
| [SPEC-F2009](mvp/SPEC-F2009-movie-select-chat.md) | 영화 선택 및 질의응답 |
| [SPEC-F2010](mvp/SPEC-F2010-domain-features.md) | 영화 특화 기능 — 관람 가이드 · 사실 여부 판정 |
| [SPEC-F2011](mvp/SPEC-F2011-condition-explore.md) | 조건 기반 영화 탐색 |
| [SPEC-F2012](mvp/SPEC-F2012-progress-notices.md) | 진행 상태 및 안내 |

### MVP — 비기능 (명세서 NF2001~NF2007)

| SPEC | 이름 |
|---|---|
| [SPEC-NF2001](mvp/SPEC-NF2001-response-time.md) | 응답 시간 |
| [SPEC-NF2002](mvp/SPEC-NF2002-collection-cache.md) | 수집 캐시 |
| [SPEC-NF2003](mvp/SPEC-NF2003-api-key-management.md) | API 키 관리 |
| [SPEC-NF2004](mvp/SPEC-NF2004-no-internal-exposure.md) | 내부 정보 비노출 |
| [SPEC-NF2005](mvp/SPEC-NF2005-module-separation.md) | 모듈 분리 (+ 테스트 · CI 기반) |
| [SPEC-NF2006](mvp/SPEC-NF2006-external-api-etiquette.md) | 외부 API 예절 |
| [SPEC-NF2007](mvp/SPEC-NF2007-source-license.md) | 출처와 이용 조건 |

### 심화 (MVP와 분리, 명세서 F2013~F2016)

| SPEC | 이름 |
|---|---|
| [SPEC-F2013](advanced/SPEC-F2013-web-frontend.md) | 프론트엔드 직접 구현 |
| [SPEC-F2014](advanced/SPEC-F2014-mmr-search.md) | MMR 검색 적용 |
| [SPEC-F2015](advanced/SPEC-F2015-rag-comparison.md) | RAG 전후 품질 비교 |
| [SPEC-F2016](advanced/SPEC-F2016-multi-source-pdf.md) | 여러 문서 출처 결합 (위키백과 + PDF) |

### 확장

[extensions/README.md](extensions/README.md) — 규칙과 후보 목록. 아직 SPEC 없음.

## ID 규칙

| 접두어 | 뜻 | 예 |
|---|---|---|
| `SPEC-F20xx` / `SPEC-NF20xx` | 명세서 요구사항 번호와 1:1 | `SPEC-F2004` |
| `SPEC-X0xx` | 확장 기능 | `SPEC-X001` |
| `AC-<번호>-nn` | 인수 조건 | `AC-F2004-03` |
| `TC-<번호>-nn` | 테스트 케이스 | `TC-F2004-05` |
| `V4.x-y` | 명세서 4장 검증 항목 (4.x절의 y번째 항목) | `V4.2-4` |
| `D-nn` | 사용자 확인을 받은 의사결정 | `D-04` |
| `A-nn` | 임의로 정한 가정 — 바꾸려면 SPEC을 먼저 고친다 | `A-10` |

테스트 이름에 TC ID를 넣는다: `def test_tc_f2004_05_item_doc_prefers_year_variant(): ...`

## 상태

| 상태 | 뜻 |
|---|---|
| Draft | 작성됨, 사용자 검토 전 |
| Approved | 사용자 승인, 이슈 생성 가능 |
| In Progress | 이슈 브랜치에서 작업 중 |
| Done | PR 머지, 모든 AC 충족 |
| Changed | Done 이후 SPEC이 바뀌어 재작업 필요 |
