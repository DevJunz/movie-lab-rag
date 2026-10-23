"""SPEC-NF2006 TC-11 — 실제 위키백과 검색 1회 (`pytest -m live`, .env의 WIKI_CONTACT 필요)."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.data.wiki_api import WikiHttpClient

pytestmark = pytest.mark.live


def test_tc_nf2006_11_real_search():
    settings = load_settings()
    assert settings.secrets.wiki_contact, ".env에 WIKI_CONTACT를 설정하세요"
    client = WikiHttpClient(settings, settings.secrets.wiki_contact)
    data = client.get({"action": "query", "list": "search", "srsearch": "블랙홀", "srlimit": 3})
    assert data["query"]["search"]
