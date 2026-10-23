# Movie Lab

영화를 고르고 질문하면 영화 메타데이터(964편)와 한국어 위키백과 문서에서 근거를 찾아 `[근거 n]`과 원문 출처를 붙여 답하는 RAG 서비스입니다.

- 스택: Python 3.10+, Streamlit, ChromaDB, LangChain, LangGraph, SSAFY GMS(OpenAI 호환)
- 작업 규칙: [AGENTS.md](AGENTS.md) · 명세: [docs/spec/](docs/spec/)

## 설치

```bash
python -m venv .venv
pip install -r requirements.txt -r requirements-dev.txt
```

## 환경 변수 (.env)

저장소 루트에 `.env`를 만들고 GMS 접속 정보를 넣습니다. 키 이름과 형식은 [docs/spec/01-architecture.md](docs/spec/01-architecture.md)의 설정 절을 따릅니다.
`.env`는 커밋하지 않습니다(`.gitignore`). 키 값을 코드 · 문서 · 이슈에 적지 마세요.

영화 데이터 팩은 SSAFY에서 따로 받아 로컬에 둡니다(저장소에 포함하지 않음).

## 실행

```bash
ruff check . && ruff format --check . && pytest              # CI와 같은 검사
pytest -m live                                               # 실제 API 테스트 (.env 필요)
python -m scripts.index_meta                                 # 영화 메타 색인
python -m scripts.collect --movie-id 157336 --question "…"   # 수집 + 색인
streamlit run movielab/ui/streamlit_app.py                   # 앱 실행
```

## 데이터 출처와 이용 조건

| 데이터 | 출처 | 이용 조건 | 지키는 방법 |
|---|---|---|---|
| 영화 메타데이터 (`movies.json`, 964편) | TMDB(The Movie Database) 기반, SSAFY 제공 가공본 | TMDB 이용약관. 교육 · 비상업 목적으로만 사용하고 TMDB 출처를 고지한다 (가정 A-15) | 화면에 TMDB 출처 고지, 근거 링크로 TMDB 페이지 표시. 원본 파일은 저장소에 포함하지 않는다 |
| 한국어 위키백과 문서 (API 수집) | `https://ko.wikipedia.org` (MediaWiki API로 수집, 수집일은 문서별 `collected_at`에 기록) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.ko) — 저작자 표시 · 동일조건변경허락 | 근거마다 문서 제목 · 원문 링크 · `CC BY-SA 4.0` 표시. 원문 JSON과 청크 메타데이터에 `url` · `source` · `license` · `collected_at` 보존 |
| 제공 위키 문서 묶음 (`movielab_wiki/`) | 한국어 위키백과, 2026-09 수집 스냅샷 | CC BY-SA 4.0 | 위와 같음. 원본 묶음은 저장소에 포함하지 않는다 |
| PDF 문서 (F2016) | 공개 PDF | 파일별 출처 · 이용 조건을 `data/pdf/pdf_manifest.json`에 기록 | 근거에 파일명 · 쪽 번호 · 출처 URL 표시 |

- TMDB 고지: This product uses the TMDB API but is not endorsed or certified by TMDB.
- 답변은 위키백과 원문을 요약 · 발췌해 만든 2차 저작물이며 원문과 다를 수 있습니다. 2차 저작물도 CC BY-SA 4.0 조건을 따릅니다.
- 원본 데이터(`movies.json`, 위키 문서 묶음, 수집한 원문)는 재배포하지 않습니다. `data/` 등은 `.gitignore`로 제외합니다.
- 테스트 픽스처는 합성 텍스트(`[합성]` 표식)만 사용하며 위키백과 원문을 복사하지 않습니다.
- 상업적 이용과 법률 검토는 이 프로젝트의 범위 밖입니다.
