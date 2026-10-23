"""SPEC-F2012 §3.2 — 시작 점검 health.check: 키 유무 · 색인 건수."""

from __future__ import annotations

import pytest

from movielab.config import Secrets, Settings
from movielab.services.health import HealthStatus, check


class FakeStore:
    def __init__(self, counts: dict[str, int]) -> None:
        self.counts = counts

    def count(self, name: str) -> int:
        return self.counts.get(name, 0)


def _settings(tmp_settings, secrets: Secrets) -> Settings:
    return Settings(tmp_settings.raw, tmp_settings.source, secrets)


@pytest.mark.parametrize(
    ("secrets", "counts", "expected"),
    [
        (Secrets("k", "https://gms.example.invalid"), {"movie_meta": 12, "wiki_docs": 34},
         HealthStatus(api_key_ok=True, meta_count=12, docs_count=34)),
        (Secrets(None, "https://gms.example.invalid"), {"movie_meta": 12},
         HealthStatus(api_key_ok=False, meta_count=12, docs_count=0)),
        (Secrets("k", None), {}, HealthStatus(api_key_ok=False, meta_count=0, docs_count=0)),
    ],
)  # fmt: skip
def test_tc_f2012_07_health(tmp_settings, secrets, counts, expected):
    assert check(_settings(tmp_settings, secrets), FakeStore(counts)) == expected


def test_tc_f2012_07_health_store_error_counts_zero(tmp_settings):
    class Broken:
        def count(self, name):
            raise RuntimeError("chroma 열기 실패")

    status = check(_settings(tmp_settings, Secrets("k", "u")), Broken())
    assert status == HealthStatus(api_key_ok=True, meta_count=0, docs_count=0)
