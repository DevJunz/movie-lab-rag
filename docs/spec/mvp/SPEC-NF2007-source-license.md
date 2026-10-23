# SPEC-NF2007 출처와 이용 조건

| 항목 | 내용 |
|---|---|
| 요구사항 | **NF2007** 출처와 이용 조건 (법 · 윤리) |
| 구분 | MVP (비기능) |
| 상태 | Draft |
| 담당 모듈 | `README.md`(데이터 출처 절), `movielab/ui/streamlit_app.py`(출처 고지), `movielab/rag/citations.py`(근거 라이선스 표시), `tests/unit/test_license_docs.py` |
| 선행 SPEC | SPEC-F2008 |
| 관련 ISSUE | (생성 후 기입) |

## 1. 요구사항 원문

> 수집한 데이터와 문서의 출처와 이용 조건을 기록하고 지켜야 한다.

## 2. 상세 명세

### 2.1 기록 (문서)

`README.md`의 `## 데이터 출처와 이용 조건` 절에 [00-product-overview.md §6](../00-product-overview.md#6-데이터-출처와-이용-조건-nf2007)의 표를 옮기고 아래를 포함한다.

| 데이터 | 기록할 내용 |
|---|---|
| 영화 메타데이터 | 출처 TMDB, SSAFY 제공 가공본, 이용 조건(교육 · 비상업, 출처 고지), 공개 저장소에 원본 미포함, TMDB 고지 문구 "This product uses the TMDB API but is not endorsed or certified by TMDB." |
| 한국어 위키백과 | 출처 URL, 라이선스 CC BY-SA 4.0 (`https://creativecommons.org/licenses/by-sa/4.0/deed.ko`), 수집 방법(API, 수집일), 답변은 원문을 요약 · 발췌한 2차 저작물이라는 점 |
| 제공 문서 묶음 | 2026-09 스냅샷, 위와 같은 라이선스, 원본 미포함 |
| PDF (F2016) | 파일별 출처 · 이용 조건은 `data/pdf/pdf_manifest.json`과 README 표 |

### 2.2 지키기 (화면 · 데이터)

| 규칙 | 구현 |
|---|---|
| 위키 근거마다 저작자 표시 | 근거 목록에 문서 제목 + 원문 링크 + `CC BY-SA 4.0` (F2008) |
| 수집 문서에 출처 보존 | 원문 JSON · 청크 메타데이터에 `url`, `source`, `license`, `collected_at` (F2004, F2005) |
| 앱 전체 고지 | 사이드바 하단에 `DomainProfile.attribution_notice`: "영화 정보: TMDB · 문서: 한국어 위키백과(CC BY-SA 4.0). 답변은 문서를 바탕으로 생성한 요약이며 원문과 다를 수 있습니다." |
| 원본 데이터 재배포 안 함 | `.gitignore`(NF2003), 제출 zip 제외 |
| 테스트 픽스처 | 합성 텍스트만 사용(위키 원문 복사 금지) |

## 3. 가정

| ID | 내용 |
|---|---|
| A-15 | TMDB 이용 조건 해석 (README 작성 시 실제 약관 재확인) |

## 4. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-NF2007-01 | README에 모든 데이터 출처와 이용 조건이 기록되어 있다 | V4.7-7 |
| AC-NF2007-02 | 위키 근거에는 항상 제목 · 원문 링크 · 라이선스가 함께 표시된다 | V4.7-7 |
| AC-NF2007-03 | 색인된 모든 위키 청크에 `url` · `license` 메타데이터가 있다 | V4.7-7 |
| AC-NF2007-04 | 앱 화면에 출처 고지가 항상 보인다 | V4.7-7 |
| AC-NF2007-05 | 테스트 픽스처에 실제 위키 원문이 없다 | — |

## 5. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-NF2007-01 | 단위 | README의 `## 데이터 출처와 이용 조건` 절 검사 | `TMDB`, `CC BY-SA 4.0`, `ko.wikipedia.org`, 고지 문구 존재 | 01 | `tests/unit/test_license_docs.py` |
| TC-NF2007-02 | 통합 | 근거 표시 렌더링(F2008 테스트와 공유) | 위키 근거마다 라이선스 문자열 | 02 | `tests/integration/test_ui_answer.py` |
| TC-NF2007-03 | 통합 | 색인 후 모든 `wiki_docs` 메타데이터 | `url` · `license` 빈 값 없음 | 03 | `tests/integration/test_doc_index.py` |
| TC-NF2007-04 | 통합 | `AppTest` 첫 화면 | 사이드바 출처 고지 문구 | 04 | `tests/integration/test_ui_chat.py` |
| TC-NF2007-05 | 단위 | 픽스처 파일에 `ko.wikipedia.org/wiki/` 실제 URL과 긴 원문 없음 (합성 표식 `[합성]` 포함) | 통과 | 05 | `tests/unit/test_license_docs.py` |

## 6. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.7-7 | README 해당 절 + 근거 표시 화면 | 검증 결과 문서 |

## 7. 범위 밖

- 법률 검토. 상업적 이용.
