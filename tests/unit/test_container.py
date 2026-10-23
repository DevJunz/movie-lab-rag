"""SPEC-NF2005 TC-10 — 조립 지점은 주입한 의존성을 그대로 쓴다."""

from __future__ import annotations

import pytest

from movielab.container import build_services
from movielab.data.domain_movie import MOVIE_PROFILE
from tests.fakes import BOOK_PROFILE, FakeChatModel, FakeEmbeddings, FakeHttpSession


def test_tc_nf2005_10_injected_dependencies_are_used(tmp_settings):
    llm, emb, http = FakeChatModel(), FakeEmbeddings(), FakeHttpSession()
    services = build_services(
        tmp_settings, llm=llm, embeddings=emb, http=http, profile=BOOK_PROFILE
    )
    assert services.llm is llm
    assert services.embeddings is emb
    assert services.http is http
    assert services.profile is BOOK_PROFILE
    assert services.settings is tmp_settings


def test_tc_nf2005_10_default_profile_is_movie(tmp_settings):
    services = build_services(tmp_settings, llm=FakeChatModel(), embeddings=FakeEmbeddings())
    assert services.profile is MOVIE_PROFILE


def test_tc_nf2003_08_build_without_key_then_lazy_error(tmp_settings):
    from movielab.core.errors import MissingApiKeyError

    services = build_services(tmp_settings)  # 키가 없어도 생성은 성공 (안내 화면을 띄우기 위해)
    with pytest.raises(MissingApiKeyError):
        _ = services.llm
    with pytest.raises(MissingApiKeyError):
        _ = services.embeddings


def test_tc_nf2003_08_real_models_created_once(tmp_path, monkeypatch):
    from movielab.config import load_settings

    monkeypatch.setenv("GMS_API_KEY", "sk-test-0123456789abcdefghijklmnop")
    monkeypatch.setenv("GMS_BASE_URL", "https://gms.example.invalid/v1")
    services = build_services(load_settings())
    assert services.llm is services.llm
    assert services.embeddings is services.embeddings
