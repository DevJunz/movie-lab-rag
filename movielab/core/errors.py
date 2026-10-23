"""사용자에게 안내해야 하는 상황을 나타내는 예외. 화면 문구는 `code`로 고른다 (F2012, NF2004)."""

from __future__ import annotations


class MovieLabUserError(Exception):
    """사용자 안내가 필요한 오류. 메시지는 로그용이고, 화면에는 `code`에 맞는 안내 문구를 보인다."""

    code = "GENERIC_ERROR"


class MissingApiKeyError(MovieLabUserError):
    """GMS API 키 또는 주소가 설정되지 않았다."""

    code = "API_KEY_MISSING"


class DataNotFoundError(MovieLabUserError):
    """항목 메타데이터 파일이 없다 (제공 데이터 팩 미설치 등)."""

    code = "DATA_MISSING"


class DataFormatError(MovieLabUserError):
    """항목 메타데이터 파일의 형식이 잘못되었다 (JSON 오류, 배열이 아님)."""

    code = "DATA_INVALID"


class InvalidApiKeyError(MovieLabUserError):
    """GMS가 키를 거부했다 (틀린 키 · 권한 없음). 다시 시도해도 같은 결과다."""

    code = "API_KEY_INVALID"


class DataEmptyError(MovieLabUserError):
    """불러온 항목이 0건이다. 빈 데이터로 기존 색인을 지우지 않도록 작업을 멈춘다."""

    code = "DATA_EMPTY"


class ExternalSourceUnavailableError(MovieLabUserError):
    """외부 문서 출처(위키백과 API 등)를 쓸 수 없다 — 연락처 없음, 차단, 재시도 소진."""

    code = "SOURCE_UNAVAILABLE"


class IndexEmptyError(MovieLabUserError):
    """항목 메타데이터 색인이 비어 있다 — 색인 스크립트를 먼저 실행해야 한다."""

    code = "INDEX_EMPTY"


class ItemNotFoundError(MovieLabUserError):
    """요청한 항목 ID가 데이터에 없다 (F2009)."""

    code = "ITEM_NOT_FOUND"


class ItemNotIndexedError(MovieLabUserError):
    """선택한 항목의 메타 청크가 색인에 없다."""

    code = "ITEM_NOT_INDEXED"
