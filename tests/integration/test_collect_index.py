"""SPEC-F2005 §3.4 — container의 수집기가 문서를 청크로 색인하고, 캐시가 청크 수를 확인한다."""

from __future__ import annotations

from movielab.container import build_services
from tests.fakes import FakeChatModel, FakeEmbeddings, pick_titles

QUESTION = "블랙홀 묘사는 실제 물리와 얼마나 다른가?"


def test_tc_f2005_10_collector_indexes_chunks_and_cache_checks(tmp_settings):
    tmp_settings.raw["collect"]["source"] = "bundle"
    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀")})
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    item = services.catalog.get("157336")
    report = services.collector.collect(item, QUESTION)
    store = services.store
    assert report.indexed_chunks > 0
    assert store.count_where("wiki_docs", {"movie_id": "157336"}) == report.indexed_chunks
    assert "CACHE_HIT" in services.collector.collect(item, QUESTION).notices
    # 색인이 사라지면(예: data/chroma 삭제) 캐시를 믿지 않고 다시 수집한다
    store.delete_collection("wiki_docs")
    again = services.collector.collect(item, QUESTION)
    assert "CACHE_HIT" not in again.notices and again.indexed_chunks > 0


def test_tc_f2005_19_bad_key_during_collect_shows_key_notice(tmp_settings):
    import httpx
    import openai
    import pytest

    from movielab.core.errors import InvalidApiKeyError

    def auth_error():
        request = httpx.Request("POST", "https://gms.example.invalid/v1/embeddings")
        return openai.AuthenticationError(
            "bad key", response=httpx.Response(401, request=request), body=None
        )

    tmp_settings.raw["collect"]["source"] = "bundle"
    llm = FakeChatModel(
        rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀", "웜홀")}
    )
    emb = FakeEmbeddings(fail_when=lambda texts: True, error=auth_error)
    services = build_services(tmp_settings, llm=llm, embeddings=emb)
    with pytest.raises(InvalidApiKeyError):
        services.collector.collect(services.catalog.get("157336"), QUESTION)
    assert emb.calls == 1  # 문서마다 임베딩을 반복 호출하지 않는다


def test_tc_f2005_26_movie_without_indexed_docs_still_hits_cache(tmp_settings):
    from movielab.collect.collector import Collector
    from movielab.collect.query_extractor import QueryExtractor
    from movielab.collect.selector import CandidateSelector
    from movielab.data.domain_movie import MOVIE_PROFILE
    from movielab.data.raw_store import RawStore
    from tests.fakes import make_manifest
    from tests.fakes.source import FakeSource, make_doc

    source = FakeSource()  # 항목 자체 문서 없음
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": "[]"})
    collector = Collector(
        api_source=source,
        bundle_source=FakeSource("bundle"),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
        manifest=make_manifest(tmp_settings.path("manifest")),
        indexer=lambda doc: 1,
        has_chunks=lambda item_id: False,  # 색인한 문서가 없으니 청크도 없다
    )
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    item = services.catalog.get("157336")
    first = collector.collect(item, QUESTION)
    assert first.indexed_titles == []
    assert "CACHE_HIT" in collector.collect(item, QUESTION).notices


def test_tc_f2005_29_blank_item_doc_rejected_and_cache_hits(tmp_settings):
    from movielab.collect.collector import Collector
    from movielab.collect.query_extractor import QueryExtractor
    from movielab.collect.selector import CandidateSelector
    from movielab.data.domain_movie import MOVIE_PROFILE
    from movielab.data.raw_store import RawStore
    from tests.fakes import make_manifest
    from tests.fakes.source import FakeSource, make_doc

    source = FakeSource()
    source.add(
        make_doc("1", "인터스텔라", text="  "),
        title_intro="[합성] 인터스텔라는 2014년 개봉한 크리스토퍼 놀란 감독의 SF 영화이다.",
    )
    source.add(make_doc("2", "블랙홀"), queries=["블랙홀"])
    llm = FakeChatModel(rules={"검색어 추출": '["블랙홀"]', "후보 선별": pick_titles("블랙홀")})

    def indexer(doc):
        if not doc.text.strip():
            raise ValueError("본문이 비어 있다")
        return 1

    collector = Collector(
        api_source=source,
        bundle_source=FakeSource("bundle"),
        extractor=QueryExtractor(llm, MOVIE_PROFILE, tmp_settings),
        selector=CandidateSelector(llm, MOVIE_PROFILE, tmp_settings),
        raw_store=RawStore(tmp_settings.path("raw_dir")),
        profile=MOVIE_PROFILE,
        settings=tmp_settings,
        manifest=make_manifest(tmp_settings.path("manifest")),
        indexer=indexer,
        has_chunks=lambda item_id: True,
    )
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    item = services.catalog.get("157336")
    first = collector.collect(item, QUESTION)
    assert ("1", "too_short") in {(r.page_id, r.reason) for r in first.rejected}
    assert "CACHE_HIT" in collector.collect(item, QUESTION).notices
