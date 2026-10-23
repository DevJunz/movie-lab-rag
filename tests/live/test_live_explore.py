"""SPEC-F2011 TC-06 — 실제 GMS · 실제 메타 색인으로 조건 탐색 (`pytest -m live`)."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live


def test_tc_f2011_06_nineties_korean_thriller():
    services = build_services(load_settings())
    if services.store.count("movie_meta") == 0:
        pytest.skip("메타 색인이 비어 있다 (scripts.index_meta 먼저)")
    result = services.explore.search("1990년대 한국 스릴러")
    print(result.parsed, [(i.item.display_name, i.reason) for i in result.items])
    for entry in result.items:
        meta = entry.item.metadata
        assert 1990 <= meta["year"] <= 1999
        assert meta["original_language"] == "ko"
