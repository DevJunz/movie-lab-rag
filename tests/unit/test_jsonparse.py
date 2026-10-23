"""LLM 출력 JSON 파싱 (SPEC-F2003 TC-08, 01-architecture §7)."""

from __future__ import annotations

import pytest

from movielab.core.jsonparse import parse_json_array, parse_json_object


@pytest.mark.parametrize(
    "text,expected",
    [
        ('["a", "b"]', ["a", "b"]),
        ('설명입니다 ["a"] 끝', ["a"]),
        ('```json\n["a"]\n```', ["a"]),
        ("[]", []),
        ("[[1, 2], [3]]", [[1, 2], [3]]),
        ('[{"movie_id": "1", "reason": "[근거]"}]', [{"movie_id": "1", "reason": "[근거]"}]),
    ],
)
def test_tc_f2003_08_parse_json_array_valid(text, expected):
    assert parse_json_array(text) == expected


@pytest.mark.parametrize("text", ["", "없음", "[깨진", '{"a": 1}', None, '["a",]x]'])
def test_tc_f2003_08_parse_json_array_invalid_returns_default(text):
    assert parse_json_array(text) is None
    assert parse_json_array(text, default=[]) == []


@pytest.mark.parametrize(
    "text,expected",
    [
        ('{"verdict": "사실"}', {"verdict": "사실"}),
        ('결과: ```json\n{"a": [1, 2]}\n```', {"a": [1, 2]}),
    ],
)
def test_tc_f2003_08_parse_json_object_valid(text, expected):
    assert parse_json_object(text) == expected


@pytest.mark.parametrize("text", ["", "[1]", "{깨진", None])
def test_tc_f2003_08_parse_json_object_invalid(text):
    assert parse_json_object(text, default={"x": 0}) == {"x": 0}
