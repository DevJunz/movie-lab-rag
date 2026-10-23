"""문자열 정규화 공통 함수."""

from __future__ import annotations

import unicodedata


def normalize_key(text: str) -> str:
    """비교용 키: 유니코드 NFC, 앞뒤 공백 제거, 연속 공백 1칸, 소문자 (NF2002 §3.2와 같은 규칙)."""
    return " ".join(unicodedata.normalize("NFC", text).split()).lower()
