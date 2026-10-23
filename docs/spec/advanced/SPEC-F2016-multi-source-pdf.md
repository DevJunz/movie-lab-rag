# SPEC-F2016 여러 문서 출처 결합 (위키백과 + PDF)

| 항목 | 내용 |
|---|---|
| 요구사항 | **F2016** 여러 문서 출처 결합 (수집 · 심화) |
| 구분 | 심화 |
| 상태 | In Progress |
| 담당 모듈 | `movielab/data/pdf_source.py`(매니페스트 · 쪽별 추출), `movielab/index/pdf_indexer.py`(PDF 청킹 · 색인), `movielab/rag/pdf_search.py`(PDF 검색 · 점수 순 결합), `movielab/rag/retriever.py`(결합 호출만), `movielab/core/messages.py`(근거 표시), `scripts/index_pdf.py` |
| 선행 SPEC | SPEC-F2005, SPEC-F2006, SPEC-F2008 |
| 관련 ISSUE | #22 |

## 1. 요구사항 원문

> 종류가 다른 문서 출처를 함께 색인하고 근거에 출처 종류를 구분한다.

명세서 3장 세부 조건:
- ◆ 종류가 다른 문서 출처(예: 위키백과와 PDF)를 함께 색인해야 한다.
- ◆ 근거에 문서 출처의 종류를 구분하여 표시해야 한다.
- ◆ 출처 종류에 따라 수집 · 청킹 방식을 달리했다면 그 이유를 설명해야 한다.

## 2. 상세 명세

### 2.1 PDF 준비 (D-08, 가정 A-12)

- 사용자가 공개 PDF를 `data/pdf/`에 넣고 `data/pdf/pdf_manifest.json`에 기록한다. 저장소에는 매니페스트 **예시**(`docs/verification/pdf_manifest.example.json`)만 둔다.
- 후보 예: 영화진흥위원회 연간 보고서 · 영화 관련 공공기관 공개 자료 등 이용 조건이 명시된 PDF. 어떤 PDF를 쓸지는 구현 이슈에서 확정하고 이 SPEC에 기록한다.

```json
[{
  "doc_id": "kofic2014",
  "file": "kofic_2014_annual.pdf",
  "title": "2014년 한국 영화산업 결산",
  "source_url": "https://…",
  "license": "공공누리 제1유형 (출처표시)",
  "movie_ids": ["282631", "396535"],
  "pages": "all"
}]
```

- `movie_ids`는 이 PDF를 근거로 쓸 영화들이다. 색인할 때 영화마다 청크를 따로 만든다(검색 필터 `movie_id` 규칙 유지).

### 2.2 수집 · 청킹 (위키와 다르게 한 부분과 이유)

| 항목 | 위키백과 | PDF | 다르게 한 이유 |
|---|---|---|---|
| 수집 | 질문마다 P1 · P2로 검색 · 선별 | 사전 지정 파일을 `scripts.index_pdf`로 일괄 색인 | PDF는 검색 API가 없고 양이 정해져 있다 |
| 텍스트 추출 | API 평문 | `pypdf`로 **쪽별** 추출, 쪽마다 반복되는 머리말 · 꼬리말 줄(3쪽 이상 반복) 제거, 하이픈 줄바꿈 연결 | PDF 텍스트는 레이아웃 잡음이 많다 |
| 청킹 | 문서 전체를 1,000 / 200 | **쪽 안에서만** 800 / 100 (`pdf_chunk_size`, `pdf_chunk_overlap`) | 근거에 쪽 번호를 정확히 표시하려면 청크가 쪽을 넘으면 안 된다. 표 · 짧은 문단이 많아 더 작게 자른다 |
| 청크 ID | `{movie_id}:{page_id}:{순번}` | `{movie_id}:pdf:{doc_id}:{쪽}:{순번}` | 쪽 번호 포함 |
| 컬렉션 | `wiki_docs` | `pdf_docs` | 재색인 · 청킹 설정을 독립적으로 바꾸기 위해 |
| 원문 출처 | URL | 파일명 + 쪽 번호 (+ `source_url`) | 명세서 F2004 "URL 또는 파일명과 쪽" |

텍스트가 거의 없는 쪽(스캔 이미지, 50자 미만)은 건너뛰고 보고서에 남긴다(OCR은 범위 밖).

### 2.3 검색 결합

- 근거 = 메타 1 + 위키 Top-k(4) + PDF Top-k(`pdf_top_k`=2), 각각 `movie_id` 필터.
- 병합 순서: 메타 → 위키와 PDF를 점수 순으로 섞음(같은 임베딩 · 코사인이라 점수 비교 가능) → 중복 제거 → 번호 부여.
- `pdf_docs`가 비어 있거나 그 영화의 PDF 청크가 없으면 MVP와 같은 결과.

### 2.3.1 구현 보완 (착수 시 코드를 읽고 정한 것)

- **모듈 분리**: 위키 색인기(`DocIndexer`)에 분기를 넣지 않고 `index/pdf_indexer.py`의 `PdfIndexer`로 따로 둔다. 쪽 단위 청킹 · 청크 ID · 지울 옛 청크 범위(`movie_id` + `doc_id`)가 위키와 달라 한 클래스에 넣으면 분기가 많아진다. 배치 쓰기(`indexing.batch_size`), 새 청크를 먼저 쓰고 이번 분할에 없는 옛 청크만 지우는 규칙은 위키와 같다.
- **검색 결합 위치**: PDF 검색 · 병합은 `rag/pdf_search.py`의 함수로 두고 `Retriever.retrieve`는 위키 병합 결과에 그 함수를 한 번 부른다(MMR 작업(F2014)과 충돌을 줄이려고 `retriever.py` 변경을 최소화). 외부 근거(위키 + PDF)를 점수 내림차순으로 다시 세운 뒤 중복 제거 · 번호 부여를 다시 한다. 점수가 없는 근거(코사인이 아닌 컬렉션)는 뒤로 보낸다.
- **설정**: `paths.pdf_manifest`(기본 `data/pdf/pdf_manifest.json`), `pdf.min_page_chars`(50, 텍스트가 거의 없는 쪽 기준), `pdf.repeat_line_min_pages`(3, 머리말 · 꼬리말 판정 쪽 수)를 `config/settings.json`에 더하고 `retrieval.pdf_top_k`(0 이상 정수, 0이면 PDF 검색 안 함)를 검증한다.
- **근거 자료형**: `Evidence`에 `file`(PDF 파일명, 기본 `None`)을 더한다. `page`는 이미 있다. 메타데이터에는 `doc_id`, `file`, `page`, `title`, `url`(=`source_url`), `license`, `source_kind="pdf"`, `source_type="PDF"`를 둔다.
- **출처 라벨 `PDF`**: 도메인과 무관한 라벨이라 `core/messages.py`의 `PDF_SOURCE_LABEL`에 둔다. 표시 형식 `{title} ({file}, p.{page})`도 messages의 함수(`evidence_title`)로 만들고, 스크립트 근거 목록(`scripts.collect`)과 프롬프트 근거 블록이 이 함수를 쓴다.
- **화면 · API**: F2009(화면) · F2013(API)이 아직 없으므로 TC-F2016-04는 근거 표시 함수와 `scripts.collect` 근거 목록 출력으로 검증한다. 화면 표시는 F2009/F2013이 같은 함수를 쓰게 한다.
- **사용할 PDF**: 이 PR에서는 실제 PDF를 확정하지 않는다(저장소에 넣지 않음). 이용 조건이 명시된 공개 PDF(예: 영화진흥위원회 공개 보고서, 공공누리 제1유형)를 사용자가 `data/pdf/`에 두고 매니페스트에 기록한다 — TC-F2016-07(수동)에서 확정해 이 절에 적는다.
- **합성 PDF 생성**: 테스트 실행 중 `tests/fakes/pdf.py`가 표준 Type1 글꼴(Helvetica)로 ASCII 텍스트 PDF를 바이트로 직접 만든다(새 의존성 없음). 바이너리 픽스처는 저장소에 넣지 않는다.

### 2.4 근거 표시

| 출처 유형 | 표시 |
|---|---|
| 영화 메타데이터 | `[근거 1] 영화 메타데이터 · 인터스텔라 (2014) · TMDB ↗` |
| 위키백과 | `[근거 2] 위키백과 · 블랙홀 · 원문 ↗ · CC BY-SA 4.0` |
| PDF | `[근거 3] PDF · 2014년 한국 영화산업 결산 (kofic_2014_annual.pdf, p.12) · 원문 ↗ · 공공누리 제1유형` |

P3 근거 블록의 출처 유형 라벨도 `PDF`로 붙는다(F2007).

## 3. 가정

| ID | 내용 |
|---|---|
| A-12 | `data/pdf/` + 매니페스트, 800 / 100, PDF Top-k 2 |
| A-12 | `pypdf==6.21.2`로 고정 (명세서 미지정, 구현 시점 최신 안정판 · Python 3.10 지원 · 순수 Python이라 CI에 추가 시스템 의존성 없음) |
| A-12 | 텍스트 50자 미만 쪽은 건너뜀, 3쪽 이상에서 반복되는 줄을 머리말 · 꼬리말로 제거 (설정 `pdf.*`) |

## 4. 인수 조건

| ID | 조건 | 명세서 4장 |
|---|---|---|
| AC-F2016-01 | 위키 청크와 PDF 청크가 함께 색인되고 한 번의 질문에서 함께 검색된다 | V4.5-4 |
| AC-F2016-02 | 근거 목록에 출처 종류(`영화 메타데이터` / `위키백과` / `PDF`)가 구분되어 표시되고, PDF 근거에는 파일명과 쪽 번호가 있다 | V4.5-4 |
| AC-F2016-03 | PDF 청크는 쪽을 넘지 않고 청크 ID에 쪽 번호가 있다 | — |
| AC-F2016-04 | 청킹 · 수집 방식이 다른 이유가 설계문서에 설명되어 있다 | — |
| AC-F2016-05 | PDF가 없어도 MVP 동작이 그대로다 | — |
| AC-F2016-06 | (필수 구현과 비교) 같은 질문에 위키만 / 위키 + PDF 근거 목록 비교가 있다 | 4.8 |

## 5. 테스트 케이스

| ID | 수준 | 시나리오 | 기대 결과 | AC | 위치 |
|---|---|---|---|---|---|
| TC-F2016-01 | 단위 | 테스트 중 생성한 3쪽짜리 합성 PDF 추출 | 쪽 번호별 텍스트, 반복 머리말 제거 | 03 | `tests/unit/test_pdf_source.py` |
| TC-F2016-02 | 통합 | 합성 PDF를 영화 2편에 색인 | 청크 ID `{movie_id}:pdf:{doc_id}:{쪽}:{순번}`, 영화별로 존재, 청크가 쪽을 넘지 않음 | 03 | `tests/integration/test_pdf_index.py` |
| TC-F2016-03 | 통합 | 위키 + PDF 색인 후 검색 | 근거에 `wiki`와 `pdf` 출처가 함께, 메타가 `[근거 1]` | 01 | `tests/integration/test_multi_source.py` |
| TC-F2016-04 | 통합 | 근거 표시 함수 · `scripts.collect` 근거 목록 (화면 · API는 F2009/F2013) | PDF 근거에 `PDF`, 파일명, `p.` 쪽 번호 | 02 | 〃 |
| TC-F2016-05 | 통합 | `pdf_docs` 비어 있음 | MVP와 같은 근거 목록 | 05 | 〃 |
| TC-F2016-06 | 단위 | 텍스트 없는 쪽 | 건너뛰고 보고서에 기록 | 03 | `tests/unit/test_pdf_source.py` |
| TC-F2016-07 | 수동 | 실제 PDF로 대표 질문 실행 | 위키만 / 위키 + PDF 근거 비교 캡처 | 02, 06 | 스크린샷 |
| TC-F2016-08 | 수동 | 설계문서 검토 | §2.2 표(수집 · 추출 · 청킹 · ID · 컬렉션을 다르게 한 이유)가 설계문서에 옮겨져 있음 | 04 | `docs/deliverables/02_RAG_파이프라인_설계.md` |

> 합성 PDF는 테스트 실행 중에 만든다(바이너리 픽스처를 저장소에 넣지 않음). 생성 방법은 구현 PR에서 정한다.

## 6. 증빙

| 항목 | 방법 | 저장 위치 |
|---|---|---|
| V4.5-4 | 출처 종류가 섞인 근거 목록 화면 | `docs/verification/screenshots/V4.5-4_multi_source.png` |

## 7. 범위 밖

- OCR, PDF 자동 검색 · 다운로드, 공공데이터 API.
