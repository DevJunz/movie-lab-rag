# 03. 제출물과 SPEC의 연결 (명세서 6장)

| 항목 | 내용 |
|---|---|
| 문서 종류 | SPEC 공통 문서 — 제출물을 어떤 SPEC · 문서 · 실행 결과에서 만드는지 |
| 원칙 | 제출 문서는 **새로 쓰지 않고 SPEC과 실행 결과에서 옮겨 만든다.** SPEC이 원본이고, 제출 문서는 그 시점의 요약본이다 |
| 상태 | Draft |

---

## 1. 제출물 지도

```text
docs/spec/ (원본: 무엇을 만들기로 했나)          docs/verification/ (증거: 실제로 됐나)
  00 제품 개요 · 결정 · 가정 ─┐                     questions.json, latency.md,
  01 아키텍처 · 데이터 · 테스트 ─┼─→ docs/deliverables/ ←─ screenshots/, retrieval_compare/
  02 대조표                   │      01_요구사항정의서.md     CI junit 결과 (GitHub Actions)
  mvp/ · advanced/ SPEC ──────┘      02_RAG_파이프라인_설계.md
  docs/dev-log.md (문제 · 해결 기록) ─→ 03_검증결과.md
                                     04_RAG_전후_비교.md
README.md ← 00 · NF2003 · NF2007 · 스크립트 사용법
소스코드  ← movielab/ · scripts/ · web/ · tests/
```

## 2. 제출물별 구성

### 2.1 요구사항 정의서 → `docs/deliverables/01_요구사항정의서.md`

| 명세서 6장 요구 | 가져올 곳 |
|---|---|
| 필수 · 심화 기능 요구사항 정리 | 각 SPEC의 §1(원문) · §2(도메인 표현) 요약 |
| 기능별 요구사항 표(F2001~) | [02-traceability.md §1](02-traceability.md#1-요구사항--spec-11) (요구사항 · SPEC · 모듈 · 상태) |
| 선택한 도메인과 조건 충족 근거 | [00-product-overview.md §2](00-product-overview.md#2-도메인-확정-명세서-21) (항목 수), §6 (문서 출처 · 이용 조건), §3 (근거가 필요한 질문) |
| (덧붙임) 의사결정 · 가정 | 00-product-overview §7 · §8 |

### 2.2 RAG 파이프라인 설계문서 → `docs/deliverables/02_RAG_파이프라인_설계.md`

| 명세서 6장 요구 | 가져올 곳 |
|---|---|
| 두 Vector DB 컬렉션 구조와 메타데이터 필드 | 01-architecture §5, SPEC-F2002 §3, SPEC-F2005 §3.2 |
| 문서 수집 · 청킹 · 색인 흐름 | 01-architecture §3, SPEC-F2003, SPEC-F2004 §3.3, SPEC-F2005 §3.1 |
| 검색 결과 병합과 중복 제거 | SPEC-F2006 §3.1 |
| 프롬프트 세 개의 역할과 출력 형식 | 01-architecture §7, SPEC-F2003 §3.1, SPEC-F2004 §3.6, SPEC-F2007 §3.3 |
| 청크 크기 · 중복 · Top-k를 정한 이유와 바꿨을 때의 차이 | 00-product-overview D-04(이유) + **실험 결과** V4.2-5(청크 수 비교), V4.3-1(Top-k 근거 비교) |
| 답변에 근거를 표시하는 방식 | SPEC-F2008 |
| 도메인 특화 기능 설계 이유 | SPEC-F2010 §2 |
| 컬렉션 · 청킹 · 프롬프트 선택 이유, 겪은 문제와 해결 | 01-architecture(선택 이유) + `docs/dev-log.md`(PR마다 쌓은 문제 · 해결 기록) |
| (심화) MMR · PDF 결합 설계 | SPEC-F2014 §2, SPEC-F2016 §2.2 (청킹을 다르게 한 이유) |

### 2.3 검증 결과 → `docs/deliverables/03_검증결과.md`

| 명세서 6장 요구 | 가져올 곳 |
|---|---|
| 4장 확인 항목별 실행 결과 화면 | 각 SPEC §7 증빙 → `docs/verification/screenshots/V4.x-y_*.png` |
| 요구사항 대조표 | 02-traceability §1 (상태 · 이슈 열 채운 최종본) |
| 테스트 결과표 | 02-traceability §3 양식 + CI `reports/junit.xml` + live 테스트 실행 기록 |
| 셀프 · 상호 체크리스트 | 3일차 오후 제공 양식. 행을 검증 ID(V4.x-y)에 맞춰 기록, 상호 점검자 이름 · 결과 포함 |
| 제출 전 점검 목록 확인 결과 | 이 문서 §3 |
| (심화) 필수 구현과의 결과 비교 | F2013: Streamlit vs 웹 기능 대응표 / F2014: 유사도 vs MMR 표 / F2015: 04 보고서 / F2016: 위키만 vs 위키 + PDF 근거 비교 |

### 2.4 구현 소스코드

| 명세서 6장 요구 | 위치 |
|---|---|
| Python 소스 | `movielab/` (영역별 패키지, 01-architecture §2) |
| 데이터 수집 및 색인 스크립트 | `scripts/index_meta.py`, `collect.py`, `prewarm.py`, `reindex_docs.py`, `index_pdf.py` |
| 심화 기능 코드 | `movielab/api/`, `web/`, `scripts/compare_retrieval.py`, `compare_rag.py`, `movielab/data/pdf_source.py` |
| (덧붙임) 테스트 | `tests/` — CI에서 자동 실행 |

### 2.5 셀프 체크리스트

3일차 오후 배포 양식을 받으면 `docs/deliverables/03_검증결과.md`의 체크리스트 절에 옮긴다. 양식의 항목을 검증 ID(V4.x-y)와 대응시켜, 증빙 위치를 SPEC §7에서 가져온다.

### 2.6 README.md (저장소 루트)

| 명세서 6장 요구 | 가져올 곳 |
|---|---|
| 프로젝트 개요 및 실행 방법 | 00-product-overview §1 · §4, NF2003 §3.2(`.env` 설정), 실행 명령(`streamlit run movielab/ui/streamlit_app.py`, `uvicorn movielab.api.server:app`) |
| 전체 기능 설명(필수 / 심화 구분) | 02-traceability §1의 두 표 |
| 데이터 준비 및 색인 절차 요약 | SPEC-F2002 §3.2, SPEC-F2004 §3.7, SPEC-F2005 §3.4, SPEC-F2016 (`index_pdf`) |
| 사용한 데이터 · 문서의 출처와 이용 조건 | SPEC-NF2007 §2.1 (`## 데이터 출처와 이용 조건` 절, 테스트로 검사) |
| 심화 기능 적용 요약 | `docs/spec/advanced/` 각 SPEC 요약 + 비교 결과 링크 |

### 2.7 추가 제출 문서

| 문서 | 근거 SPEC |
|---|---|
| `docs/deliverables/04_RAG_전후_비교.md` | SPEC-F2015 (명세서 4.6 "비교 결과를 문서로 작성하여 제출물에 포함") |

## 3. 제출 전 점검 목록 (명세서 4.8)

| # | 점검 항목 | 확인 방법 | 결과 |
|---|---|---|---|
| 1 | 필수 기능 F2001 ~ F2012가 모두 동작한다 | 02-traceability 상태 전부 Done + CI 통과 + 수동 증빙 | |
| 2 | 선택한 심화 기능이 동작하고, 필수 기능의 결과와 비교되어 있다 | F2013~F2016 AC 중 "필수 구현과 비교" 항목 | |
| 3 | 증명을 위한 스크린샷 항목을 모두 첨부했다 | 각 SPEC §7 목록 ↔ `docs/verification/screenshots/` 파일 대조 | |
| 4 | 요구사항 정의서 · RAG 파이프라인 설계문서 · 소스코드 · README.md를 모두 포함했다 | §2.1 · 2.2 · 2.4 · 2.6 | |
| 5 | 검증 결과(요구사항 대조표, 테스트 결과표, 셀프 · 상호 체크리스트)를 포함했다 | §2.3 · 2.5 | |
| 6 | (추가) 제출 zip에 `.env` · `data/` · 데이터 팩 · 대외비 문서가 없다 | zip 목록 확인 (NF2003 TC-NF2003-06) | |

## 4. 제출 파일 만들기

- 파일 이름: `AI 코어프로젝트 2_Movie Lab_지역_반_성명.zip` (지역 · 반 · 성명은 제출 시 채움).
- `git archive`는 Git이 추적하는 파일만 묶으므로 `.gitignore` 대상(`.env`, `data/`, 데이터 팩, `prd.pdf`)이 자동으로 빠진다.

```bash
git archive --format=zip -o "AI 코어프로젝트 2_Movie Lab_지역_반_성명.zip" main
```

- 업로드: lab.ssafy.com.
