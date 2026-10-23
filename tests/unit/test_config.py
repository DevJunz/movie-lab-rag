"""설정 로드 (SPEC-NF2005 TC-09).

키 관리(NF2003) · 값 검증(F2005 등) 테스트는 각 SPEC PR에서 추가한다.
"""

from __future__ import annotations

import copy
import json
import pickle
from pathlib import Path

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
