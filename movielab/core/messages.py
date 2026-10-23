"""사용자에게 보이는 안내 문구 (F2012, NF2004). 문구는 코드 대신 여기서만 가져온다.

문구는 템플릿이다. `{item_label}` 같은 자리표시자는 DomainProfile 라벨로 채운다.
화면 · 스크립트에는 이 문구만 보이고, 예외 메시지 · traceback은 로그에만 남긴다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

# 스크립트 근거 목록 (SPEC-F2006 V4.3-1)
EVIDENCE_LIST_HEADER = "근거:"
EVIDENCE_LIST_LINE = "[근거 {n}] {source_type} · {title}{score}"
EVIDENCE_LIST_SCORE = " · 점수 {score:.3f}"

# PDF 근거 (SPEC-F2016 §2.4) — 출처 유형 라벨과 제목 형식 `제목 (파일명, p.쪽)`
PDF_SOURCE_LABEL = "PDF"
PDF_EVIDENCE_TITLE = "{title} ({file}, p.{page})"


def evidence_title(evidence: Any) -> str:
    """근거 목록 · 프롬프트에 보일 제목. PDF 근거는 파일명과 쪽 번호를 붙인다."""
    if getattr(evidence, "file", None) and getattr(evidence, "page", None) is not None:
        return PDF_EVIDENCE_TITLE.format(
            title=evidence.title, file=evidence.file, page=evidence.page
        )
    return str(evidence.title)


# 근거로 답할 수 없을 때 답변이 그대로 써야 하는 문장 (SPEC-F2007 §3.3)
NOT_FOUND = "제공된 문서에서 확인되지 않습니다."

# 질의응답 화면 (SPEC-F2009)
APP_TITLE = "Movie Lab"
MENU_ASK = "질문하기"
MENU_EXPLORE = "조건 탐색"
SELECT_ITEM_LABEL = "{item_label} 선택"
SELECT_ITEM_FIRST = "{item_label}를 먼저 선택하세요."
ASK_PLACEHOLDER = "{item_name}에 대해 질문하세요"
INDEX_COUNTS = "색인: {item_label} {items}건 / 문서 {chunks}청크"
CLEAR_HISTORY = "이 {item_label} 대화 지우기"
ANSWERING = "답변을 준비하고 있습니다…"

# 진행 상태 (SPEC-F2012 §3.1) — 단계 키 → 문구. 모르는 단계는 표시하지 않는다
PROGRESS = {
    "cache_hit": "이미 수집한 질문입니다. 저장된 문서로 답합니다.",
    "extract_queries": "검색어를 고르는 중…",
    "extract_queries_done": "검색어: {queries}",
    "resolve_item_doc": "{item_label} 문서를 찾는 중…",
    "search": "{doc_source_label}에서 후보 문서를 찾는 중… ({current}/{total} 검색어)",
    "filter": "후보 문서를 정리하는 중…",
    "select": "읽을 문서를 고르는 중…",
    "fetch": "문서 본문을 가져오는 중… ({current}/{total})",
    "index": "문서를 색인하는 중…",
    "retrieve": "근거를 찾는 중…",
    "generate": "답변을 작성하는 중…",
    "done": "완료 — 수집한 문서: {titles} (버린 문서 {rejected}건)",
    "done_none": "완료 — 새로 수집한 문서 없음 (버린 문서 {rejected}건)",
    "explore_parse": "조건을 해석하는 중…",
    "explore_search": "후보를 찾는 중…",
    "explore_select": "조건에 맞는 {item_label}를 고르는 중…",
}
STATUS_RUNNING = "문서를 확인하고 답변을 준비하는 중…"
STATUS_DONE = "완료 ({seconds:.1f}초)"
STATUS_FAILED = "처리하지 못했습니다"
COLLECT_DETAIL_QUERIES = "검색어: {queries}"
COLLECT_DETAIL_INDEXED = "색인한 문서: {titles}"
COLLECT_DETAIL_REJECTED = "버린 문서: {items}"
NONE_MARK = "없음"

# 조건 탐색 화면 (SPEC-F2011)
EXPLORE_INPUT_LABEL = "찾고 싶은 {item_label}의 조건"
EXPLORE_PLACEHOLDER = "예: 1990년대 한국 스릴러, 우주를 배경으로 한 가족 {item_label}"
EXPLORE_BUTTON = "찾기"
EXPLORE_SUMMARY = "후보 {candidates}건 중 조건에 맞는 {count}건"
EXPLORE_REASON = "선정 이유: {reason}"
EXPLORE_ASK_BUTTON = "이 {item_label}로 질문하기"

# 근거 목록 (SPEC-F2008 §3.3)
EVIDENCE_HEADER = "근거"
EVIDENCE_SOURCE_LINK = "원문"
UNCITED = "이 답변에는 인용된 근거가 없습니다."

TEMPLATES: dict[str, str] = {
    "API_KEY_MISSING": (
        "GMS API 키가 설정되지 않았습니다. .env 파일에 GMS_API_KEY와 GMS_BASE_URL을 "
        "설정한 뒤 다시 실행하세요."
    ),
    "API_KEY_INVALID": (
        "GMS API 키가 올바르지 않거나 권한이 없습니다. .env의 GMS_API_KEY와 GMS_BASE_URL을 "
        "확인하세요. 기존 색인은 그대로 두었습니다."
    ),
    "DATA_EMPTY": (
        "불러온 {item_label} 데이터가 0건입니다. 데이터 파일을 확인하세요. "
        "기존 색인은 그대로 두었습니다."
    ),
    "DATA_MISSING": (
        "{item_label} 데이터 파일을 찾을 수 없습니다. 제공 데이터 팩을 저장소 루트에 두었는지, "
        "config/settings.json의 paths.movies 경로를 확인하세요."
    ),
    "DATA_INVALID": (
        "{item_label} 데이터 파일의 형식이 올바르지 않습니다. JSON 배열인지 확인하세요."
    ),
    "SETTINGS_INVALID": (
        "설정 파일을 읽을 수 없습니다. config/settings.json(또는 MOVIELAB_SETTINGS가 "
        "가리키는 파일)의 형식과 값을 확인하세요."
    ),
    "SOURCE_UNAVAILABLE": "외부 문서 출처에 연결할 수 없습니다. 잠시 후 다시 시도하세요.",
    "ITEM_NOT_FOUND": "ID {item_id}인 {item_label}을(를) 찾을 수 없습니다.",
    "GENERIC_ERROR": "처리 중 문제가 발생했습니다. 잠시 후 다시 시도하세요.",
    # 색인 안내 (SPEC-F2006 AC-07 · 08, 화면 표시는 SPEC-F2012)
    "INDEX_EMPTY": (
        "{item_label} 색인이 비어 있습니다. 터미널에서 python -m scripts.index_meta를 실행하세요."
    ),
    "ITEM_NOT_INDEXED": (
        "이 {item_label}은(는) 아직 색인되지 않았습니다. "
        "python -m scripts.index_meta를 다시 실행하세요."
    ),
    "NO_EXTERNAL_DOCS": (
        "관련 {doc_source_label} 문서를 찾지 못했습니다. {meta_source_label}만으로 답합니다."
    ),
    "EXPLORE_EMPTY": "조건에 맞는 {item_label}를 찾지 못했습니다. 조건을 바꿔 보세요.",
    "SOURCE_FALLBACK": (
        "{doc_source_label}에 연결할 수 없어 미리 수집된 문서 묶음을 사용했습니다."
    ),
    # 스크립트 인자 오류
    "ARG_NOT_INTEGER": "정수가 아닙니다: {value}",
    "ARG_NOT_POSITIVE": "1 이상이어야 합니다: {value}",
    "CACHE_RESET": "수집 캐시를 지웠습니다: {target}",
    "CACHE_RESET_ALL": "수집 캐시를 모두 지웠습니다.",
    "REINDEX_REPORT": (
        "chunk_size={chunk_size} overlap={chunk_overlap} → 문서 {documents}건 / 청크 {chunks}개 "
        "(컬렉션 전체 {total_chunks}개)"
    ),
    "REINDEX_FAILED": "색인하지 못한 문서 {failed}건 — 로그(logs/)를 확인하고 다시 실행하세요.",
    "PDF_MANIFEST_MISSING": (
        "PDF 매니페스트가 없습니다: {path}. data/pdf/에 PDF를 두고 pdf_manifest.json에 기록하세요 "
        "(예시: docs/verification/pdf_manifest.example.json)."
    ),
    "PDF_MANIFEST_INVALID": "PDF 매니페스트 형식이 올바르지 않습니다: {path}",
    "PDF_FILE_MISSING": "PDF 파일이 없어 건너뜁니다: {file}",
    "PDF_REPORT": "{file}: 쪽 {pages}개 · 청크 {chunks}개 색인 (건너뛴 쪽: {skipped})",
    "PDF_TOTAL": "PDF 색인 완료: 문서 {documents}건 · 청크 {chunks}개 (컬렉션 전체 {total}개)",
    "REINDEX_REMOVED": "저장 원문이 없는 문서 {removed}건의 청크를 지웠습니다.",
    "REINDEX_OVERRIDE_NOTICE": (
        "설정 파일과 다른 청크 값으로 색인했습니다. 이후 수집되는 문서는 설정 값으로 색인되어 "
        "크기가 섞이니, 비교가 끝나면 인자 없이 다시 실행해 되돌리세요."
    ),
    "REINDEX_BAD_CHUNKING": (
        "청크 크기는 1 이상, 청크 중복은 0 이상이고 크기보다 작아야 합니다 "
        "(크기 {chunk_size}, 중복 {chunk_overlap})."
    ),
    "REINDEX_EMPTY": (
        "다시 색인할 저장 원문이 없습니다. 먼저 문서를 수집하세요 (python -m scripts.collect)."
    ),
    "CACHE_RESET_FAILED": (
        "수집 캐시를 지우지 못했습니다. "
        "다른 프로그램이 사용 중일 수 있으니 잠시 후 다시 시도하세요."
    ),
    # 색인 스크립트 출력 (F2002)
    "INDEX_REPORT": "로드 {loaded}건 / 색인 {indexed}건 / 건너뜀 {skipped}건",
    "INDEX_FAILED_BATCHES": "실패한 배치: {batches} — 다시 실행하면 빠진 항목만 채워집니다.",
    "INDEX_MISMATCH": (
        "로드한 항목 수와 색인 건수가 맞지 않습니다. 로그(logs/)를 확인하고, "
        "계속 맞지 않으면 --rebuild로 색인을 다시 만드세요."
    ),
    "INDEX_REMOVED": "데이터에서 빠진 항목의 문서 {removed}건을 지웠습니다.",
}

DEFAULT_LABELS = {"item_label": "항목"}
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")


def render(code: str, labels: Mapping[str, str] | None = None, **values: Any) -> str:
    """안내 코드에 맞는 문구. 모르는 코드는 일반 오류 문구로 바꾼다."""
    template = TEMPLATES.get(code, TEMPLATES["GENERIC_ERROR"])
    mapping = {**DEFAULT_LABELS, **(labels or {}), **values}
    return _PLACEHOLDER.sub(
        lambda m: str(mapping[m.group(1)]) if m.group(1) in mapping else m.group(0), template
    )
