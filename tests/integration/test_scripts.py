"""실행 스크립트 통합 테스트."""

from __future__ import annotations

import json

from scripts import index_meta


def test_tc_f2001_10_show_prints_index_text(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--show", "157336"]) == 0
    out = capsys.readouterr().out
    assert "제목: 인터스텔라 (2014)" in out
    assert "감독: 크리스토퍼 놀란" in out
    assert len([line for line in out.splitlines() if ": " in line]) >= 8


def test_tc_f2001_10_show_unknown_id(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--show", "999999999"]) == 1
    assert "찾을 수 없" in capsys.readouterr().out


def test_tc_f2001_10_missing_data_file(tmp_settings, tmp_path, monkeypatch, capsys):
    raw = dict(tmp_settings.raw)
    raw["paths"] = {**raw["paths"], "movies": str(tmp_path / "없음.json")}
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "데이터" in out and "Traceback" not in out
