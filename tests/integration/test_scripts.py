"""실행 스크립트 통합 테스트."""

from __future__ import annotations

import json

import pytest

from scripts import index_meta


def test_tc_f2001_10_show_prints_index_text(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--show", "157336"]) == 0
    out = capsys.readouterr().out
    assert "제목: 인터스텔라 (2014)" in out
    assert "감독: 크리스토퍼 놀란" in out
    labels = [line.split(":")[0] for line in out.splitlines()]
    assert labels == ["제목", "원제", "장르", "감독", "출연", "제작 국가", "원어", "줄거리"]


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


def _settings_with_movies(tmp_settings, tmp_path, content: str):
    movies = tmp_path / "movies_bad.json"
    movies.write_text(content, encoding="utf-8")
    raw = dict(tmp_settings.raw)
    raw["paths"] = {**raw["paths"], "movies": str(movies)}
    path = tmp_path / "settings_bad.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("content", ["[{깨진", '{"movie_id": "1"}'])
def test_tc_f2001_12_bad_data_file_no_traceback(
    tmp_settings, tmp_path, monkeypatch, capsys, content
):
    path = _settings_with_movies(tmp_settings, tmp_path, content)
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "형식" in out and "Traceback" not in out


def test_tc_f2001_12_bad_settings_file_no_traceback(tmp_path, monkeypatch, capsys):
    broken = tmp_path / "broken_settings.json"
    broken.write_text("{설정 아님", encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(broken))
    assert index_meta.main(["--show", "157336"]) == 1
    out = capsys.readouterr().out
    assert "설정" in out and "Traceback" not in out
