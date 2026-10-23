"""SPEC-F2010 TC-09 — 실제 GMS로 명량 사실 판정 (`pytest -m live`)."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live


def test_tc_f2010_09_myeongnyang_claim():
    services = build_services(load_settings())
    if services.store.count("movie_meta") == 0:
        pytest.skip("메타 색인이 비어 있다 (scripts.index_meta 먼저)")
    result = services.factcheck.check("282631", "조선 수군의 배는 12척이었다")
    print(result.verdict, result.reason, [e.title for e in result.cited])
    assert result.verdict in ("사실", "거짓", "확인 불가")
    if result.verdict in ("사실", "거짓"):
        assert len(result.cited) >= 1
