"""사용자에게 안내해야 하는 상황을 나타내는 예외. 화면 문구는 `code`로 고른다 (F2012, NF2004)."""

from __future__ import annotations


class MovieLabUserError(Exception):
    """사용자 안내가 필요한 오류. 메시지는 로그용이고, 화면에는 `code`에 맞는 안내 문구를 보인다."""

    code = "GENERIC_ERROR"


class MissingApiKeyError(MovieLabUserError):
    """GMS API 키 또는 주소가 설정되지 않았다."""

    code = "API_KEY_MISSING"
