"""SPEC-F2005 위키백과 문서 색인 (RAG 2) — 청킹 · 청크 ID · 메타데이터 · 재색인."""

from __future__ import annotations

import dataclasses
import json

import pytest

from movielab.config import load_settings
from movielab.container import build_services
from movielab.index.doc_indexer import DocIndexer
from tests.fakes import FakeEmbeddings
from tests.fakes.source import make_doc

REQUIRED = {
    "movie_id", "page_id", "title", "url", "related_movie", "search_query", "collected_at",
    "is_item_doc", "chunk_index", "chunk_size", "chunk_overlap", "source_kind", "source_type",
    "license",
}  # fmt: skip


def _doc(movie_id="157336", page_id="20671", length=3000, title="블랙홀"):
    paragraph = "[합성] 블랙홀은 중력이 매우 강한 천체이다. " * 10  # 약 280자
    text = "\n\n".join([paragraph] * (length // len(paragraph) + 1))[:length]
    return dataclasses.replace(
        make_doc(page_id, title, text=text), movie_id=movie_id, related_movie="인터스텔라",
        search_query="블랙홀", collected_at="2026-10-23",
    )  # fmt: skip


def _services(settings):
    return build_services(settings, embeddings=FakeEmbeddings())


def _settings_with(tmp_settings, tmp_path, **chunking):
    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["chunking"].update(chunking)
    path = tmp_path / f"settings_{chunking.get('chunk_size', 'x')}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return load_settings(path)


def test_tc_f2005_01_chunks_respect_size_and_ids(tmp_settings):
    services = _services(tmp_settings)
    count = DocIndexer(services.store).index_document(_doc())
    store = services.store
    ids = sorted(store.ids("wiki_docs"), key=lambda i: int(i.rsplit(":", 1)[1]))
    assert count == len(ids) >= 4
    assert ids == [f"157336:20671:{n}" for n in range(count)]
    docs = store.get_by_ids("wiki_docs", ids)
    assert all(len(d.page_content) <= 1000 for d in docs)


def test_tc_f2005_02_separate_collection_from_meta(tmp_settings):
    services = _services(tmp_settings)
    DocIndexer(services.store).index_document(_doc())
    assert services.store.count("wiki_docs") > 0
    assert services.store.count("movie_meta") == 0
    assert services.store.distance("wiki_docs") == "cosine"


def test_tc_f2005_03_metadata_fields(tmp_settings):
    services = _services(tmp_settings)
    DocIndexer(services.store).index_document(dataclasses.replace(_doc(), is_item_doc=True))
    for doc in services.store.get_by_ids("wiki_docs", services.store.ids("wiki_docs")):
        meta = doc.metadata
        assert REQUIRED <= set(meta)
        assert meta["movie_id"] == "157336" and meta["page_id"] == "20671"
        assert isinstance(meta["page_id"], str) and isinstance(meta["chunk_index"], int)
        assert meta["source_kind"] == "wiki" and meta["source_type"] == "위키백과"
        assert meta["license"] == "CC BY-SA 4.0" and meta["url"].startswith("https://")
        assert meta["is_item_doc"] is True
        assert (meta["chunk_size"], meta["chunk_overlap"]) == (1000, 200)


def test_tc_f2005_04_shared_document_not_overwritten(tmp_settings):
    services = _services(tmp_settings)
    indexer = DocIndexer(services.store)
    a = indexer.index_document(_doc(movie_id="157336"))
    b = indexer.index_document(_doc(movie_id="27205"))
    store = services.store
    assert store.count("wiki_docs") == a + b
    assert store.count_where("wiki_docs", {"movie_id": "157336"}) == a
    assert store.count_where("wiki_docs", {"movie_id": "27205"}) == b


def test_tc_f2005_05_settings_change_chunk_count(tmp_settings, tmp_path):
    big = _services(tmp_settings)
    count_big = DocIndexer(big.store).index_document(_doc())
    small_settings = _settings_with(tmp_settings, tmp_path, chunk_size=500, chunk_overlap=100)
    small = _services(small_settings)
    count_small = DocIndexer(small.store).index_document(_doc())
    assert count_small > count_big
    meta = small.store.get_by_ids("wiki_docs", ["157336:20671:0"])[0].metadata
    assert (meta["chunk_size"], meta["chunk_overlap"]) == (500, 100)


def test_tc_f2005_06_reindex_with_bigger_chunks_leaves_no_stale(tmp_settings, tmp_path):
    small_settings = _settings_with(tmp_settings, tmp_path, chunk_size=500, chunk_overlap=100)
    small = _services(small_settings)
    many = DocIndexer(small.store).index_document(_doc())
    big = _services(tmp_settings)  # 같은 Chroma 폴더, 1000/200
    few = DocIndexer(big.store).index_document(_doc())
    assert few < many
    assert big.store.count("wiki_docs") == few
    assert f"157336:20671:{many - 1}" not in big.store.ids("wiki_docs")


@pytest.mark.parametrize(
    "chunking",
    [
        {"chunk_size": 200, "chunk_overlap": 200},
        {"chunk_size": 0, "chunk_overlap": 0},
        {"chunk_size": "1000"},
        {"chunk_overlap": -1},
        {"pdf_chunk_size": 100, "pdf_chunk_overlap": 100},
    ],
)
def test_tc_f2005_07_invalid_chunking_rejected(tmp_settings, tmp_path, chunking):
    from movielab.config import SettingsError

    with pytest.raises(SettingsError):
        _settings_with(tmp_settings, tmp_path, **chunking)


def test_tc_f2005_04_delete_document(tmp_settings):
    services = _services(tmp_settings)
    indexer = DocIndexer(services.store)
    indexer.index_document(_doc(movie_id="157336"))
    keep = indexer.index_document(_doc(movie_id="27205"))
    removed = indexer.delete_document("157336", "20671")
    assert removed > 0 and services.store.count("wiki_docs") == keep
