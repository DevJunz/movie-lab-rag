"""SPEC-NF2003 TC-11 — live 테스트는 격리 없이 실제 .env 키를 본다 (`pytest -m live`로만 실행)."""

from __future__ import annotations

import pytest

from movielab.config import load_settings

pytestmark = pytest.mark.live


def test_tc_nf2003_11_live_tests_see_real_keys():
    secrets = load_settings().secrets
    assert secrets.has_gms, ".env에 GMS_API_KEY와 GMS_BASE_URL을 설정하세요"
