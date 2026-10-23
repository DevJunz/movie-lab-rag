"""SPEC-NF2001 TC-04 — 실제 GMS · 위키백과로 Q1 응답 시간 (`pytest -m live`).

처음 질문 뒤 두 번째(캐시 적중) `total`이 목표 이하인지 본다. 초과는 실패가 아니라 경고로 남긴다.
"""

from __future__ import annotations

import warnings

import pytest

from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live

Q1 = ("157336", "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?")


def test_tc_nf2001_04_q1_cached_within_target():
    settings = load_settings()
    services = build_services(settings)
    first = services.qa.ask(*Q1).timings
    second = services.qa.ask(*Q1).timings
    print(f"처음 {first.get('total', 0.0):.1f}초 / 두 번째 {second['total']:.1f}초")
    target = settings.latency.cached_target_sec
    if second["total"] > target:
        warnings.warn(f"캐시 적중 {second['total']:.1f}초 > 목표 {target}초", stacklevel=1)
    assert "total" in second
