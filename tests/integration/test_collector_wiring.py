"""SPEC-F2004 TC-24 — 수집기는 한 번만 만들고, --dry-run 수집기는 색인 · 캐시 기록이 없다."""

from __future__ import annotations

from movielab.collect.manifest import NullManifest
from movielab.container import build_services
from tests.fakes import FakeChatModel


def test_tc_f2004_24_collector_cached_and_dry_run(tmp_settings):
    services = build_services(tmp_settings, llm=FakeChatModel())
    assert services.collector is services.collector
    dry = services.make_collector(dry_run=True)
    assert dry.indexer is None and type(dry.manifest) is NullManifest
    assert dry.bundle_source is services.collector.bundle_source  # 묶음은 한 번만 로드
