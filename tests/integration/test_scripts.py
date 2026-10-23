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


# --- SPEC-F2002 색인 · 건수 · 재색인 ---


def _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, embeddings=None, **indexing):
    """스크립트가 가짜 임베딩과 (필요하면 indexing 값을 바꾼) 임시 설정을 쓰게 한다."""
    from movielab.container import build_services
    from tests.fakes import FakeEmbeddings

    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["indexing"].update(indexing)
    path = tmp_path / "settings_index.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(path))
    emb = embeddings or FakeEmbeddings()
    monkeypatch.setattr(
        index_meta, "build_services", lambda settings: build_services(settings, embeddings=emb)
    )
    return emb


def test_tc_f2002_05_index_count_and_rebuild(tmp_settings, tmp_path, monkeypatch, capsys):
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    assert "로드 12건 / 색인 12건 / 건너뜀 0건" in capsys.readouterr().out
    assert index_meta.main([]) == 0  # 재실행 안전
    assert "색인 12건" in capsys.readouterr().out
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out
    assert index_meta.main(["--rebuild"]) == 0
    assert "색인 12건" in capsys.readouterr().out


def test_tc_f2002_06_failed_batch_exit_code(tmp_settings, tmp_path, monkeypatch, capsys):
    from tests.fakes import FakeEmbeddings

    broken = FakeEmbeddings(fail_when=lambda texts: any("인셉션" in t for t in texts))
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, broken, retry_wait_sec=0)
    assert index_meta.main(["--batch-size", "5"]) == 1
    out = capsys.readouterr().out
    assert "실패한 배치" in out and "Traceback" not in out


def test_tc_f2002_10_count_without_key(tmp_settings, monkeypatch, capsys):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 0" in capsys.readouterr().out


def test_tc_f2002_11_no_key_keeps_existing_index(tmp_settings, tmp_path, monkeypatch, capsys):
    from movielab.container import build_services

    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    capsys.readouterr()
    # 이제 키도 임베딩 주입도 없는 상태로 색인 · 재색인
    monkeypatch.setattr(index_meta, "build_services", lambda settings: build_services(settings))
    for argv in ([], ["--rebuild"]):
        assert index_meta.main(argv) == 1
        out = capsys.readouterr().out
        assert "GMS_API_KEY" in out and "Traceback" not in out
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out  # 기존 색인 유지


@pytest.mark.parametrize("value", ["0", "-5", "abc"])
def test_tc_f2002_14_batch_size_must_be_positive(tmp_settings, monkeypatch, value):
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    with pytest.raises(SystemExit) as exit_info:
        index_meta.main(["--batch-size", value])
    assert exit_info.value.code == 2


def test_tc_f2002_11_invalid_key_message_and_index_kept(
    tmp_settings, tmp_path, monkeypatch, capsys
):
    import httpx
    import openai

    from tests.fakes import FakeEmbeddings

    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main([]) == 0
    capsys.readouterr()

    def auth_error():
        request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
        return openai.AuthenticationError(
            "bad", response=httpx.Response(401, request=request), body=None
        )

    bad = FakeEmbeddings(fail_when=lambda texts: True, error=auth_error)
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path, bad)
    assert index_meta.main(["--rebuild"]) == 1
    out = capsys.readouterr().out
    assert "올바르지 않" in out and "잠시 후" not in out and "Traceback" not in out
    _use_fake_embeddings(monkeypatch, tmp_settings, tmp_path)
    assert index_meta.main(["--count"]) == 0
    assert "movie_meta: 12" in capsys.readouterr().out
