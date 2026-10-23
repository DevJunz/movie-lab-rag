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


@pytest.mark.parametrize(
    "text,expected",
    [
        # 배열 뒤 설명에 대괄호가 있어도 앞의 배열을 읽는다 (PR #29 리뷰)
        ('["블랙홀"]\n(참고: [1] 위키백과)', ["블랙홀"]),
        # 앞에 JSON이 아닌 대괄호가 있으면 건너뛴다
        ('설명 [근거 1] 이후 ["a"]', ["a"]),
        ('```\n["a", "b"]\n```\n끝 [x]', ["a", "b"]),
    ],
)
def test_tc_f2003_08_first_valid_json_value_wins(text, expected):
    assert parse_json_array(text) == expected


def test_tc_f2003_08_wrong_outer_shape_is_default():
    assert parse_json_object('[{"verdict": "사실"}]', default="기본") == "기본"
    assert parse_json_array('{"verdict": "사실", "citations": [1]}', default="기본") == "기본"
    assert parse_json_object('{"verdict": "사실", "citations": [1]} 끝 [2]') == {
        "verdict": "사실",
        "citations": [1],
    }
