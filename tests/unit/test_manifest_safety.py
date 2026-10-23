"""SPEC-NF2002 (PR #31 리뷰) — 다중 인스턴스, 구조 검증, 주입 날짜 · 백업 이름."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from movielab.collect.manifest import Manifest


def test_tc_nf2002_13_other_instance_reset_not_resurrected(tmp_path):
    path = tmp_path / "manifest.json"
    app = Manifest(path)
    app.record_keyword("1", "블랙홀")
    script = Manifest(path)
    script.reset()  # 앱이 떠 있는 동안 --reset-cache
    app.record_keyword("1", "웜홀")
    fresh = Manifest(path)
    assert fresh.has_keyword("1", "웜홀")
    assert not fresh.has_keyword("1", "블랙홀")
    assert not app.has_keyword("1", "블랙홀")  # 읽기도 파일 변경을 반영


@pytest.mark.parametrize("content", ['{"1": []}', '{"1": {"keywords": "x"}}', "[]"])
def test_tc_nf2002_14_wrong_structure_backed_up(tmp_path, content):
    path = tmp_path / "manifest.json"
    path.write_text(content, encoding="utf-8")
    manifest = Manifest(path)
    assert manifest.cached_queries("1", "q") is None
    manifest.record_keyword("1", "a")  # 예외 없이 동작
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 1


def test_tc_nf2002_14_backups_do_not_collide(tmp_path):
    fixed = datetime(2026, 10, 23, 12, 0, 0)
    path = tmp_path / "manifest.json"
    for _ in range(2):
        path.write_text("{깨짐", encoding="utf-8")
        Manifest(path, now=lambda: fixed)
    assert len(list(tmp_path.glob("manifest.json.broken-*"))) == 2


def test_tc_nf2002_14_collected_at_uses_injected_today(tmp_path):
    import json

    path = tmp_path / "manifest.json"
    Manifest(path, today=lambda: date(2026, 1, 2)).record_keyword("1", "a")
    assert json.loads(path.read_text(encoding="utf-8"))["1"]["collected_at"] == "2026-01-02"
