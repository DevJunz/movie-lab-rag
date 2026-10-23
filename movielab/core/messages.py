"""사용자에게 보이는 안내 문구 (F2012, NF2004). 문구는 코드 대신 여기서만 가져온다.

문구는 템플릿이다. `{item_label}` 같은 자리표시자는 DomainProfile 라벨로 채운다.
화면 · 스크립트에는 이 문구만 보이고, 예외 메시지 · traceback은 로그에만 남긴다.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

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
    # 스크립트 인자 오류
    "ARG_NOT_INTEGER": "정수가 아닙니다: {value}",
    "ARG_NOT_POSITIVE": "1 이상이어야 합니다: {value}",
    "CACHE_RESET": "수집 캐시를 지웠습니다: {target}",
    "CACHE_RESET_ALL": "수집 캐시를 모두 지웠습니다.",
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
