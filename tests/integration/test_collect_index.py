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
