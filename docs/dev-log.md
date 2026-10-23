# 개발 기록 — 겪은 문제와 해결

RAG 파이프라인 설계문서의 "겪은 문제, 해결 과정" 절의 원본이다(명세서 6장). PR마다 의미 있는 문제가 있었으면 한 항목씩 추가한다.

| 날짜 | SPEC · PR | 문제 | 원인 | 해결 | 관련 결정 · 가정 |
|---|---|---|---|---|---|
| 2026-10-23 | SPEC 작성 | 위키 문서 JSON의 `page_id`는 정수, 제공 매니페스트의 `page_ids`는 문자열이다 | 데이터 팩 형식 차이 | 내부에서는 항상 `str`로 정규화 (01-architecture §4.2) | — |
| 2026-10-23 | SPEC 작성 | 같은 제목의 영화가 있고(「미녀와 야수」 1991 · 2017), 괄호 없는 「미녀와 야수」 위키 문서는 영화가 아니라 동화다 | 위키백과 표제 규칙 | `제목 (연도년 영화)` → `제목 (영화)` → `제목`(조건부) 순서로 항목 자체 문서를 판별 (SPEC-F2004 §3.4) | — |
| 2026-10-23 | SPEC-NF2005 (#1) | `ruff format .`이 SPEC 마크다운 안의 Python 코드 블록까지 다시 정렬했다 | ruff 0.17은 마크다운의 코드 블록도 포맷 대상으로 본다 | `pyproject.toml`에 `include = ["*.py", "*.pyi"]`로 대상을 한정하고 문서 변경은 되돌림 | A-13 |
| 2026-10-23 | SPEC-NF2005 (#1) | 네트워크 차단 픽스처가 Windows의 `socket.socketpair()`까지 막을 수 있다 | Windows는 `socketpair`를 루프백 TCP 연결로 구현한다 | 루프백 주소는 허용하고 외부 주소 · DNS 조회만 막음 (TC-NF2005-06) | — |
| 2026-10-23 | SPEC-NF2005 (#24) | 로컬(Windows)에서는 통과한 ruff import 정렬이 CI(리눅스)에서 실패했다 | `extend-exclude = ["data"]`가 이름이 `data`인 모든 폴더에 걸려 CI에서 `movielab/data/`가 1st-party로 인식되지 않았다 | 제외 항목에서 `data`를 빼고(루트 `data/`에는 `.py`가 없음) `known-first-party`를 명시 | A-13 |
| 2026-10-23 | SPEC-NF2005 (#24) | CI에서 `movielab.data`를 import 하지 못했다. 로컬에는 있는데 저장소에 `movielab/data/`가 커밋되지 않았다 | `.gitignore`의 `data/`가 루트 `data/`뿐 아니라 `movielab/data/`까지 무시했다 | 데이터 · 산출물 경로를 `/data/`처럼 루트 기준으로 고정, 무시된 소스 파일을 잡는 회귀 테스트 TC-NF2005-11 추가 | NF2003 |
| 2026-10-23 | SPEC-NF2003 (#25) | 한국어 Windows에서 `Path.read_text()`가 `.env.example`을 읽지 못했다 | 인코딩을 주지 않으면 시스템 기본(cp949)으로 읽는다 | 파일을 읽고 쓸 때 항상 `encoding="utf-8"`을 명시 | — |
| 2026-10-23 | SPEC-NF2003 (#25) | `load_dotenv`가 `os.environ`에 값을 써서 테스트 사이에 가짜 키가 새고, 앱 실행 중 `.env`를 고쳐도 반영되지 않았다 (리뷰 지적) | `load_dotenv(override=False)`는 처음 읽은 값을 프로세스 환경에 남긴다 | `dotenv_values()`로 읽어 환경변수와 합치고 `os.environ`은 건드리지 않음 | NF2003 §3.1 |
| 2026-10-23 | SPEC-NF2003 (#25) | 환경 격리 픽스처가 live 테스트에서도 키를 지워 `pytest -m live`가 항상 실패할 구조였다 (리뷰 지적) | autouse 픽스처가 마커를 보지 않았다 | live 마커면 격리를 건너뜀, TC-NF2003-11로 확인 | — |
