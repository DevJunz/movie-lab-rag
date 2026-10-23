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


def _services(settings, embeddings=None):
    return build_services(settings, embeddings=embeddings or FakeEmbeddings())


def _indexer(store, **chunking):
    return DocIndexer(store, source_type="위키백과", **chunking)


def _settings_with(tmp_settings, tmp_path, **chunking):
    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["chunking"].update(chunking)
    path = tmp_path / f"settings_{chunking.get('chunk_size', 'x')}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return load_settings(path)


def test_tc_f2005_01_chunks_respect_size_and_ids(tmp_settings):
    services = _services(tmp_settings)
    count = _indexer(services.store).index_document(_doc())
    store = services.store
    ids = sorted(store.ids("wiki_docs"), key=lambda i: int(i.rsplit(":", 1)[1]))
    assert count == len(ids) == 4
    assert ids == [f"157336:20671:{n}" for n in range(4)]
    docs = store.get_by_ids("wiki_docs", ids)
    assert all(len(d.page_content) <= 1000 for d in docs)


def test_tc_f2005_02_separate_collection_from_meta(tmp_settings):
    services = _services(tmp_settings)
    _indexer(services.store).index_document(_doc())
    assert services.store.count("wiki_docs") > 0
    assert services.store.count("movie_meta") == 0
    assert services.store.distance("wiki_docs") == "cosine"


def test_tc_f2005_03_metadata_fields(tmp_settings):
    services = _services(tmp_settings)
    _indexer(services.store).index_document(dataclasses.replace(_doc(), is_item_doc=True))
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
    indexer = _indexer(services.store)
    a = indexer.index_document(_doc(movie_id="157336"))
    b = indexer.index_document(_doc(movie_id="27205"))
    store = services.store
    assert store.count("wiki_docs") == a + b
    assert store.count_where("wiki_docs", {"movie_id": "157336"}) == a
    assert store.count_where("wiki_docs", {"movie_id": "27205"}) == b


def test_tc_f2005_05_settings_change_chunk_count(tmp_settings, tmp_path):
    big = _services(tmp_settings)
    count_big = _indexer(big.store).index_document(_doc())
    small_settings = _settings_with(tmp_settings, tmp_path, chunk_size=500, chunk_overlap=100)
    small = _services(small_settings)
    count_small = _indexer(small.store).index_document(_doc())
    assert count_small > count_big
    meta = small.store.get_by_ids("wiki_docs", ["157336:20671:0"])[0].metadata
    assert (meta["chunk_size"], meta["chunk_overlap"]) == (500, 100)


def test_tc_f2005_06_reindex_with_bigger_chunks_leaves_no_stale(tmp_settings, tmp_path):
    small_settings = _settings_with(tmp_settings, tmp_path, chunk_size=500, chunk_overlap=100)
    small = _services(small_settings)
    many = _indexer(small.store).index_document(_doc())
    big = _services(tmp_settings)  # 같은 Chroma 폴더, 1000/200
    few = _indexer(big.store).index_document(_doc())
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


def test_tc_f2005_11_delete_document_only_that_movie(tmp_settings):
    services = _services(tmp_settings)
    indexer = _indexer(services.store)
    indexer.index_document(_doc(movie_id="157336"))
    keep = indexer.index_document(_doc(movie_id="27205"))
    removed = indexer.delete_document("157336", "20671")
    assert removed > 0 and services.store.count("wiki_docs") == keep


# --- PR #32 리뷰: 기존 색인을 잃지 않는다 · 재색인 실패 격리 · 고아 청크 정리 ---


def _auth_error():
    import httpx
    import openai

    request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
    return openai.AuthenticationError(
        "bad key", response=httpx.Response(401, request=request), body=None
    )


def test_tc_f2005_12_failed_reindex_keeps_old_chunks(tmp_settings, tmp_path):
    state = {"fail": False}
    emb = FakeEmbeddings(fail_when=lambda texts: state["fail"])
    services = _services(tmp_settings, emb)
    before = _indexer(services.store).index_document(_doc())
    ids_before = sorted(services.store.ids("wiki_docs"))
    state["fail"] = True
    small = _services(
        _settings_with(tmp_settings, tmp_path, chunk_size=500, chunk_overlap=100), emb
    )
    with pytest.raises(RuntimeError):
        _indexer(small.store).index_document(_doc())
    assert sorted(services.store.ids("wiki_docs")) == ids_before
    assert services.store.count("wiki_docs") == before


def test_tc_f2005_14_reindex_isolates_failures(tmp_settings):
    from movielab.services.indexing import reindex_documents

    emb = FakeEmbeddings(fail_when=lambda texts: any("[깨짐]" in t for t in texts))
    services = _services(tmp_settings, emb)
    good = _doc(page_id="1")
    bad = dataclasses.replace(_doc(page_id="2"), text="[깨짐] 임베딩이 실패하는 문서")
    other = _doc(page_id="3")
    report = reindex_documents([good, bad, other], _indexer(services.store))
    assert report.documents == 2 and report.failed == 1  # 성공한 문서만 센다
    assert report.chunks == services.store.count("wiki_docs") == report.total_chunks
    assert services.store.count_where("wiki_docs", {"page_id": "3"}) > 0


def test_tc_f2005_14_reindex_bad_key_raises_invalid_key(tmp_settings):
    from movielab.core.errors import InvalidApiKeyError
    from movielab.services.indexing import reindex_documents

    emb = FakeEmbeddings(fail_when=lambda texts: True, error=_auth_error)
    services = _services(tmp_settings, emb)
    with pytest.raises(InvalidApiKeyError):
        reindex_documents([_doc(page_id="1"), _doc(page_id="2")], _indexer(services.store))
    assert emb.calls == 1  # 키 오류는 다음 문서로 넘어가지 않고 바로 중단


def test_tc_f2005_15_full_reindex_removes_chunks_without_raw(tmp_settings):
    from movielab.services.indexing import reindex_documents

    services = _services(tmp_settings)
    indexer = _indexer(services.store)
    kept, dropped = _doc(page_id="1"), _doc(page_id="2")
    other_movie = _doc(movie_id="27205", page_id="9")
    for doc in (kept, dropped, other_movie):
        indexer.index_document(doc)

    scoped = reindex_documents([kept], indexer, movie_id="157336")
    assert scoped.removed == 1
    assert services.store.count_where("wiki_docs", {"page_id": "2"}) == 0
    assert services.store.count_where("wiki_docs", {"movie_id": "27205"}) > 0  # 범위 밖은 유지

    full = reindex_documents([kept], indexer)
    assert full.removed == 1
    assert services.store.count_where("wiki_docs", {"movie_id": "27205"}) == 0
    assert full.total_chunks == services.store.count("wiki_docs") == full.chunks


def test_tc_f2005_16_has_where(tmp_settings):
    services = _services(tmp_settings)
    store = services.store
    assert store.has_where("wiki_docs", {"movie_id": "157336"}) is False  # 컬렉션 없음
    _indexer(store).index_document(_doc())
    assert store.has_where("wiki_docs", {"movie_id": "157336"}) is True
    assert store.has_where("wiki_docs", {"movie_id": "27205"}) is False


def test_tc_f2005_17_source_type_is_required(tmp_settings):
    services = _services(tmp_settings)
    with pytest.raises(TypeError):
        DocIndexer(services.store)  # type: ignore[call-arg]


# --- PR #32 재리뷰: 키 확인 · 빈 본문 · 문자열 ID · 재시도 ---


def test_tc_f2005_18_reindex_without_key_stops_with_key_notice(tmp_settings):
    from movielab.core.errors import MissingApiKeyError
    from movielab.services.indexing import reindex_documents

    services = build_services(tmp_settings)  # 키 없음
    with pytest.raises(MissingApiKeyError):
        reindex_documents([_doc(page_id="1")], _indexer(services.store))


def test_tc_f2005_21_int_movie_id_stored_as_string(tmp_settings):
    services = _services(tmp_settings)
    doc = dataclasses.replace(_doc(), movie_id=157336, page_id=20671)
    indexer = _indexer(services.store)
    first = indexer.index_document(doc)
    meta = services.store.get_by_ids("wiki_docs", ["157336:20671:0"])[0].metadata
    assert meta["movie_id"] == "157336" and meta["page_id"] == "20671"
    assert services.store.has_where("wiki_docs", {"movie_id": "157336"})
    assert indexer.index_document(doc) == first
    assert services.store.count("wiki_docs") == first  # 다시 색인해도 쌓이지 않는다


def test_tc_f2005_22_empty_body_fails_and_keeps_old_chunks(tmp_settings):
    from movielab.services.indexing import reindex_documents

    services = _services(tmp_settings)
    indexer = _indexer(services.store)
    before = indexer.index_document(_doc())
    empty = dataclasses.replace(_doc(), text="  \n\n ")
    with pytest.raises(ValueError):
        indexer.index_document(empty)
    assert services.store.count("wiki_docs") == before

    report = reindex_documents([empty, _doc(page_id="2")], indexer)
    assert report.failed == 1 and report.documents == 1
    assert services.store.count_where("wiki_docs", {"page_id": "20671"}) == before


def test_tc_f2005_23_transient_error_retried(tmp_settings):
    from movielab.services.indexing import reindex_documents

    state = {"fail": 1}

    def fail_once(texts):
        state["fail"] -= 1
        return state["fail"] >= 0

    emb = FakeEmbeddings(fail_when=fail_once)
    services = _services(tmp_settings, emb)
    report = reindex_documents([_doc()], _indexer(services.store), sleep=lambda s: None)
    assert report.failed == 0 and report.documents == 1
    assert emb.calls == 2


def test_tc_f2005_23_permanent_error_not_retried(tmp_settings):
    from movielab.services.indexing import reindex_documents

    services = _services(tmp_settings)
    waits = []
    empty = dataclasses.replace(_doc(), text=" ")
    report = reindex_documents([empty], _indexer(services.store), sleep=waits.append)
    assert report.failed == 1 and waits == []


def test_tc_f2005_24_pruned_movie_manifest_reset(tmp_settings):
    from movielab.collect.manifest import Manifest
    from movielab.services.indexing import reindex_documents

    services = _services(tmp_settings)
    indexer = _indexer(services.store)
    manifest = Manifest(tmp_settings.path("manifest"))
    kept, dropped = _doc(page_id="1"), _doc(page_id="2")
    other = _doc(movie_id="27205", page_id="9")
    for doc in (kept, dropped, other):
        indexer.index_document(doc)
        manifest.record_page(doc.movie_id, doc.page_id, doc.title, 1)
    report = reindex_documents([kept, other], indexer, manifest=manifest)
    assert report.removed == 1
    assert not manifest.has_indexed_pages("157336")  # 지운 문서를 다시 수집할 수 있게
    assert manifest.has_indexed_pages("27205")


def test_tc_f2005_27_retry_classification_matches_meta_index(tmp_settings):
    import json

    import httpx
    import openai

    from movielab.services.indexing import reindex_documents

    state = {"fail": 1}

    def truncated_once(texts):
        state["fail"] -= 1
        return state["fail"] >= 0

    emb = FakeEmbeddings(
        fail_when=truncated_once, error=lambda: json.JSONDecodeError("응답 잘림", "", 0)
    )
    services = _services(tmp_settings, emb)
    report = reindex_documents([_doc()], _indexer(services.store), sleep=lambda s: None)
    assert report.failed == 0 and emb.calls == 2  # 잘린 응답은 일시 오류 — 재시도

    def bad_request():
        request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
        return openai.BadRequestError(
            "bad", response=httpx.Response(400, request=request), body=None
        )

    emb2 = FakeEmbeddings(fail_when=lambda texts: True, error=bad_request)
    other = _services(tmp_settings, emb2)
    waits = []
    report = reindex_documents([_doc(page_id="5")], _indexer(other.store), sleep=waits.append)
    assert report.failed == 1 and emb2.calls == 1 and waits == []  # 확정 오류 — 재시도 없음


def test_tc_f2005_28_prune_only_without_key(tmp_settings):
    from movielab.services.indexing import reindex_documents

    _indexer(_services(tmp_settings).store).index_document(_doc())  # 키가 있을 때 색인해 둔 청크
    keyless = build_services(tmp_settings)  # 키 없음
    report = reindex_documents([], _indexer(keyless.store))
    assert report.removed == 1
    assert keyless.store.count("wiki_docs") == 0


def test_tc_f2005_32_upsert_in_batches(tmp_settings, tmp_path):
    raw = json.loads(json.dumps(tmp_settings.raw))
    raw["chunking"].update(chunk_size=100, chunk_overlap=0)
    raw["indexing"]["batch_size"] = 2
    path = tmp_path / "settings_batch.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    services = _services(load_settings(path))
    store = services.store
    calls = []
    original = store.upsert

    def counting_upsert(name, documents):
        calls.append(len(documents))
        return original(name, documents)

    store.upsert = counting_upsert
    text = "\n\n".join(["[합성] " + "가" * 90] * 5)  # 문단 5개 → 청크 5개
    count = _indexer(store).index_document(dataclasses.replace(_doc(), text=text))
    assert count == 5
    assert calls == [2, 2, 1]
    assert store.count("wiki_docs") == 5
