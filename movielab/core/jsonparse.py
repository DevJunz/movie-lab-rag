"""LLM 출력에서 JSON 배열 · 객체를 꺼낸다 (01-architecture §7).

LLM은 설명 문장 · 코드 펜스를 섞기 쉽다. 코드 펜스를 지운 뒤, 여는 괄호가 나오는 곳마다
그 자리부터 JSON 값 하나를 읽어 본다. JSON이 아닌 괄호(예: `[근거 1]`)는 건너뛰고,
값 뒤에 붙은 설명은 무시한다. **처음 읽힌 값**의 모양이 원하는 모양이 아니면 기본값을 돌려준다
(예: 객체를 기대했는데 `[{...}]`이면 안쪽 객체를 꺼내지 않는다). 예외를 던지지 않는다.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

T = TypeVar("T")

_FENCE = re.compile(r"```[A-Za-z]*")
_DECODER = json.JSONDecoder()


def _first_json_value(text: Any) -> Any:
    if not isinstance(text, str):
        return None
    cleaned = _FENCE.sub("", text)
    for position, char in enumerate(cleaned):
        if char not in "[{":
            continue
        try:
            value, _ = _DECODER.raw_decode(cleaned, position)
        except json.JSONDecodeError:
            continue
        return value
    return None


def parse_json_array(text: Any, default: T | None = None) -> list[Any] | T | None:
    value = _first_json_value(text)
    return value if isinstance(value, list) else default


def parse_json_object(text: Any, default: T | None = None) -> dict[str, Any] | T | None:
    value = _first_json_value(text)
    return value if isinstance(value, dict) else default
