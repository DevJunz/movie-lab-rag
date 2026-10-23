"""SPEC-F2001 TC-06 — 제공 데이터 팩 movies.json 실제 로드. 데이터 팩이 없는 CI에서는 skip."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.data.movies import load_items


def test_tc_f2001_06_real_movies_json_loads_964():
    path = load_settings().path("movies")
    if not path.exists():
        pytest.skip("제공 데이터 팩이 없다 (공개 저장소에 포함하지 않음)")
    result = load_items(path)
    assert len(result.items) == 964
    assert result.skipped == 0
    assert len({item.item_id for item in result.items}) == 964
