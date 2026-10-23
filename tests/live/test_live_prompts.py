"""SPEC-F2003 TC-09 — 실제 GMS로 Q1 검색어 추출 (`pytest -m live`)."""

from __future__ import annotations

import pytest

from movielab.collect.query_extractor import QueryExtractor
from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live


def test_tc_f2003_09_real_query_extraction():
    services = build_services(load_settings())
    item = services.catalog.get("157336")
    plan = QueryExtractor(services.llm, services.profile, services.settings).extract(
        item, "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?"
    )
    print("검색어:", plan.all)
    assert not plan.fallback
    assert 1 <= len(plan.llm_queries) <= 5
