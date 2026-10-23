"""SPEC-NF2003 — GMS 채팅 · 임베딩 모델 생성. 키가 없으면 안내용 예외."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.core.errors import MissingApiKeyError, MovieLabUserError
from movielab.providers import make_chat_model, make_embeddings

FAKE_KEY = "sk-test-0123456789abcdefghijklmnop"


def test_tc_nf2003_02_missing_key_raises():
    settings = load_settings()
    with pytest.raises(MissingApiKeyError) as error:
        make_chat_model(settings)
    assert isinstance(error.value, MovieLabUserError)
    assert error.value.code == "API_KEY_MISSING"
    with pytest.raises(MissingApiKeyError):
        make_embeddings(settings)


def test_tc_nf2003_02_missing_base_url_raises(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    with pytest.raises(MissingApiKeyError):
        make_chat_model(load_settings())


def test_tc_nf2003_01_models_use_settings_and_secrets(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    settings = load_settings()
    chat = make_chat_model(settings)
    assert chat.model_name == "gpt-4o-mini"
    assert chat.temperature == 0
    assert chat.openai_api_base == "https://gms.example.invalid/v1"
    assert chat.openai_api_key.get_secret_value() == FAKE_KEY
    emb = make_embeddings(settings)
    assert emb.model == "text-embedding-3-small"
    assert emb.openai_api_base == "https://gms.example.invalid/v1"


def test_tc_nf2003_01_embeddings_timeout_and_no_tokenizer_download(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    emb = make_embeddings(load_settings())
    assert emb.request_timeout == 60
    assert emb.check_embedding_ctx_length is False


def test_tc_f2002_19_embeddings_sdk_retries_disabled(monkeypatch):
    monkeypatch.setenv("GMS_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    assert make_embeddings(load_settings()).max_retries == 0
