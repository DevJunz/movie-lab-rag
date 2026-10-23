"""SPEC-NF2005 TC-10 — 조립 지점은 주입한 의존성을 그대로 쓴다."""

from __future__ import annotations

from movielab.container import build_services
from movielab.data.domain_movie import MOVIE_PROFILE
from tests.fakes import FakeChatModel, FakeEmbeddings, FakeHttpSession
from tests.integration.test_domain_swap import BOOK_PROFILE


def test_tc_nf2005_10_injected_dependencies_are_used(tmp_settings):
    llm, emb, http = FakeChatModel(), FakeEmbeddings(), FakeHttpSession()
    services = build_services(tmp_settings, llm=llm, embeddings=emb, http=http, profile=BOOK_PROFILE)
    assert services.llm is llm
    assert services.embeddings is emb
    assert services.http is http
    assert services.profile is BOOK_PROFILE
    assert services.settings is tmp_settings


def test_tc_nf2005_10_default_profile_is_movie(tmp_settings):
    services = build_services(tmp_settings, llm=FakeChatModel(), embeddings=FakeEmbeddings())
    assert services.profile is MOVIE_PROFILE
