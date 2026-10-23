"""SPEC-NF2007 출처와 이용 조건 — 색인 메타데이터와 근거의 출처 · 라이선스 보존."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from movielab.container import build_services
from movielab.data.wiki_bundle import WikiBundleSource
from movielab.services.indexing import index_catalog
from tests.fakes import FakeClock, FakeEmbeddings

BUNDLE = Path(__file__).resolve().parents[1] / "fixtures" / "wiki_small"


def _bundle_docs():
    source = WikiBundleSource(BUNDLE)
    for path in sorted(BUNDLE.glob("*.json")):
        movie_id = path.name.split("_", 1)[0]
        page_id = str(json.loads(path.read_text(encoding="utf-8"))["page_id"])
        doc = source.fetch(page_id)
        assert doc is not None
        yield dataclasses.replace(doc, movie_id=movie_id, related_movie="영화")


def _index_bundle(services):
    indexer = services.doc_indexer()
    for doc in _bundle_docs():
        indexer.index_document(doc)


def test_tc_nf2007_03_all_wiki_chunks_keep_source_and_license(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    _index_bundle(services)
    store = services.store
    ids = list(store.ids("wiki_docs"))
    assert ids
    for chunk in store.get_by_ids("wiki_docs", ids):
        meta = chunk.metadata
        for key in ("url", "license", "source", "collected_at"):
            assert str(meta.get(key) or "").strip(), (chunk.id, key)
        assert meta["license"] == "CC BY-SA 4.0"


def test_tc_nf2007_02_wiki_evidence_has_title_url_license(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    _index_bundle(services)
    result = services.retriever().retrieve("157336", "블랙홀은 어떤 천체인가")
    wiki = [e for e in result.evidences if e.source_kind == "wiki"]
    assert wiki
    for evidence in wiki:
        assert evidence.title and evidence.url
        assert evidence.license == "CC BY-SA 4.0"
