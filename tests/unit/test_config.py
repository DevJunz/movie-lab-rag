"""설정 로드 (SPEC-NF2005 TC-09).

키 관리(NF2003) · 값 검증(F2005 등) 테스트는 각 SPEC PR에서 추가한다.
"""

from __future__ import annotations

import copy
import json
import pickle
from pathlib import Path

import pytest

from movielab.config import load_settings
from tests.conftest import REPO_ROOT


def test_tc_nf2005_09_default_settings_file():
    settings = load_settings()
    assert settings.chunking.chunk_size == 1000  # D-04
    assert settings.chunking.chunk_overlap == 200
    assert settings.retrieval.top_k == 4
    assert settings.retrieval.search_type == "similarity"
    assert settings.models.chat == "gpt-4o-mini"  # D-05
    assert settings.models.embedding == "text-embedding-3-small"
    assert settings.collections.meta == "movie_meta"
    assert settings.collections.docs == "wiki_docs"
    assert settings.collect.source == "auto"  # A-17
    # 상대 경로는 저장소 루트 기준 절대 경로로 바뀐다
    assert settings.path("chroma_dir") == (REPO_ROOT / "data" / "chroma").resolve()


def test_tc_nf2005_09_env_selects_other_file(tmp_path: Path, monkeypatch):
    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["retrieval"]["top_k"] = 7
    other = tmp_path / "other.json"
    other.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(other))
    assert load_settings().retrieval.top_k == 7


def test_tc_nf2005_09_tmp_settings_points_into_tmp_path(tmp_settings, tmp_path: Path):
    assert tmp_settings.path("chroma_dir").is_relative_to(tmp_path)
    assert tmp_settings.path("manifest").is_relative_to(tmp_path)
    assert tmp_settings.path("movies").name == "movies_small.json"


def test_tc_nf2005_09_settings_survive_copy_and_pickle():
    settings = load_settings()
    section = copy.deepcopy(settings.chunking)
    assert section.chunk_size == 1000
    assert pickle.loads(pickle.dumps(settings.retrieval)).top_k == 4
    assert pickle.loads(pickle.dumps(settings)).chunking.chunk_overlap == 200


# --- SPEC-NF2003 키 관리 ---

FAKE_KEY = "sk-test-0123456789abcdefghijklmnop"


def test_tc_nf2003_01_secrets_from_environment(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    monkeypatch.setenv("WIKI_CONTACT", "tester@example.invalid")
    secrets = load_settings().secrets
    assert secrets.gms_api_key == FAKE_KEY
    assert secrets.gms_base_url == "https://gms.example.invalid/v1"
    assert secrets.wiki_contact == "tester@example.invalid"
    assert secrets.has_gms


def test_tc_nf2003_01_empty_values_are_missing(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", "  ")
    secrets = load_settings().secrets
    assert secrets.gms_api_key is None
    assert not secrets.has_gms


def test_tc_nf2003_07_dotenv_file_loaded_without_override(tmp_path: Path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"GMS_API_KEY={FAKE_KEY}\nWIKI_CONTACT=file@example.invalid\n")
    monkeypatch.setattr("movielab.config.DOTENV_PATH", dotenv)
    monkeypatch.setenv("WIKI_CONTACT", "env@example.invalid")
    secrets = load_settings().secrets
    assert secrets.gms_api_key == FAKE_KEY  # 파일에서 읽음
    assert secrets.wiki_contact == "env@example.invalid"  # 이미 있는 환경 값은 덮어쓰지 않음


def test_tc_nf2003_07_repo_dotenv_not_read_in_tests():
    # conftest가 .env 경로를 없는 임시 경로로 바꾼다 — 개발자 PC의 실제 키가 테스트에 섞이지 않는다
    assert load_settings().secrets.gms_api_key is None


def test_tc_nf2003_03_repr_and_logs_mask_secrets(monkeypatch, caplog):
    import logging

    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    settings = load_settings()
    for text in (repr(settings), str(settings), repr(settings.secrets)):
        assert FAKE_KEY not in text
        assert "***" in text
    with caplog.at_level(logging.INFO, logger="movielab"):
        logging.getLogger("movielab").info("설정: %r / %s", settings, settings.secrets)
    assert FAKE_KEY not in caplog.text


def test_tc_nf2003_01_model_names_overridable_by_env(monkeypatch):
    monkeypatch.setenv("MOVIELAB_CHAT_MODEL", "other-chat")
    monkeypatch.setenv("MOVIELAB_EMBED_MODEL", "other-embed")
    settings = load_settings()
    assert settings.models.chat == "other-chat"
    assert settings.models.embedding == "other-embed"


def test_tc_nf2003_09_load_settings_does_not_touch_environ(tmp_path: Path, monkeypatch):
    import os

    dotenv = tmp_path / ".env"
    dotenv.write_text(f"GMS_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    monkeypatch.setattr("movielab.config.DOTENV_PATH", dotenv)
    before = dict(os.environ)
    assert load_settings().secrets.gms_api_key == FAKE_KEY
    assert dict(os.environ) == before


def test_tc_nf2003_09_dotenv_changes_picked_up_on_reload(tmp_path: Path, monkeypatch):
    dotenv = tmp_path / ".env"
    monkeypatch.setattr("movielab.config.DOTENV_PATH", dotenv)
    dotenv.write_text("GMS_API_KEY=\n", encoding="utf-8")
    assert load_settings().secrets.gms_api_key is None
    dotenv.write_text(f"GMS_API_KEY={FAKE_KEY}\n", encoding="utf-8")
    assert load_settings().secrets.gms_api_key == FAKE_KEY


# --- SPEC-F2002 indexing 설정 검증 ---


@pytest.mark.parametrize(
    "field,value", [("batch_size", 0), ("retries", -1), ("retry_wait_sec", -1)]
)
def test_tc_f2002_14_invalid_indexing_settings_rejected(tmp_path: Path, field, value):
    from movielab.config import SettingsError

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["indexing"][field] = value
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)


def test_tc_f2002_14_default_indexing_settings():
    settings = load_settings()
    assert settings.indexing.batch_size == 100  # A-21
    assert settings.indexing.retries == 1
    assert settings.indexing.retry_wait_sec == 2.0


@pytest.mark.parametrize(
    "indexing",
    [
        None,
        {"batch_size": "100", "retries": 1, "retry_wait_sec": 2.0},
        {"batch_size": 1.5, "retries": 1, "retry_wait_sec": 2.0},
        {"batch_size": True, "retries": 1, "retry_wait_sec": 2.0},
        {"batch_size": 100, "retries": True, "retry_wait_sec": 2.0},
        {"batch_size": 100, "retries": 1, "retry_wait_sec": "2"},
    ],
)
def test_tc_f2002_17_indexing_types_checked(tmp_path: Path, indexing):
    from movielab.config import SettingsError

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["indexing"] = indexing
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)


# --- SPEC-NF2006 wiki 설정 검증 ---


@pytest.mark.parametrize(
    "change",
    [
        {"max_retries": -1},
        {"project_url": None},
        {"project_url": ""},
        {"timeout_sec": 0},
        {"maxlag": "5"},
        {"min_interval_sec": True},
        {"max_retry_after_sec": -1},
    ],
)
def test_tc_nf2006_18_invalid_wiki_settings_rejected(tmp_path: Path, change):
    from movielab.config import SettingsError

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["wiki"].update(change)
    if change.get("project_url") is None and "project_url" in change:
        del raw["wiki"]["project_url"]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)


@pytest.mark.parametrize(
    "change",
    [{"card_overview_chars": 0}, {"max_queries": "5"}, {"source": "wiki"}, {"search_limit": 0}],
)
def test_tc_f2003_11_invalid_collect_settings_rejected(tmp_path: Path, change):
    from movielab.config import SettingsError

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["collect"].update(change)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)


@pytest.mark.parametrize(
    "cache",
    [
        {"lock_poll_sec": 0},
        {"io_retries": -1},
        {"lock_timeout_sec": "10"},
        {"io_retry_wait_sec": -1},
    ],
)
def test_tc_nf2002_22_cache_settings_validated(tmp_path: Path, cache):
    from movielab.config import SettingsError

    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["cache"].update(cache)
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(SettingsError):
        load_settings(path)


@pytest.mark.parametrize(
    ("key", "value", "ok"),
    [
        ("search_type", "mmr", True),
        ("search_type", "similarity", True),
        ("search_type", "mrr", False),
        ("mmr_fetch_k", 0, False),
        ("mmr_lambda", 1.5, False),
        ("mmr_lambda", "0.5", False),
    ],
)
def test_tc_f2014_03_search_type_validated(tmp_settings, tmp_path, key, value, ok):
    from movielab.config import SettingsError

    raw = copy.deepcopy(tmp_settings.raw)
    raw["retrieval"][key] = value
    path = tmp_path / "s.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    if ok:
        assert getattr(load_settings(path).retrieval, key) == value
    else:
        with pytest.raises(SettingsError):
            load_settings(path)
