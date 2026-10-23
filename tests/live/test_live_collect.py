"""SPEC-F2004 TC-14 — 실제 위키백과 + GMS로 Q1 수집 (`pytest -m live`). 원문은 임시 폴더에 저장."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live


def test_tc_f2004_14_real_collect_q1(tmp_path):
    settings = load_settings()
    settings.raw["paths"] = {**settings.raw["paths"], "raw_dir": str(tmp_path / "raw")}
    settings.raw["collect"]["source"] = "api"
    services = build_services(settings)
    item = services.catalog.get("157336")
    report = services.collector.collect(
        item, "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?"
    )
    print("검색어:", report.queries)
    print("색인 대상:", report.indexed_titles)
    print("버림:", [(r.title, r.reason) for r in report.rejected])
    assert report.source_used == "api"
    assert report.item_doc_title == "인터스텔라"
    assert report.indexed_titles[0] == "인터스텔라"
    assert all(p.exists() for p in report.saved_paths)
