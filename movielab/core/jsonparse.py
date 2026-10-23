"""LLM 출력에서 JSON 배열 · 객체를 꺼낸다 (01-architecture §7).

LLM은 설명 문장 · 코드 펜스를 섞기 쉽다. 첫 여는 괄호부터 마지막 닫는 괄호까지 잘라 읽고,
실패하면 호출자가 정한 기본값을 돌려준다(예외를 던지지 않는다).
"""

from __future__ import annotations

import json
from typing import Any, TypeVar

T = TypeVar("T")


def _slice_json(text: Any, open_char: str, close_char: str) -> Any:
    if not isinstance(text, str):
        return None
    start, end = text.find(open_char), text.rfind(close_char)
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def parse_json_array(text: Any, default: T | None = None) -> list[Any] | T | None:
    value = _slice_json(text, "[", "]")
    return value if isinstance(value, list) else default


def parse_json_object(text: Any, default: T | None = None) -> dict[str, Any] | T | None:
    value = _slice_json(text, "{", "}")
    return value if isinstance(value, dict) else default
