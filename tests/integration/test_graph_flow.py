"""SPEC-F2007 TC-02 — 실제 Retriever(임시 Chroma) + 가짜 LLM으로 그래프 실행."""

from __future__ import annotations

import dataclasses

from movielab.container import build_services
from movielab.rag.graph import build_graph
from movielab.services.indexing import index_catalog
from tests.fakes import FakeChatModel, FakeClock, FakeEmbeddings
from tests.fakes.source import make_doc


def test_tc_f2007_02_invoke_fills_contexts_and_answer(tmp_settings):
    llm = FakeChatModel(rules={"답변 생성": "블랙홀은 빛도 못 빠져나오는 천체다 [근거 2]."})
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    doc = dataclasses.replace(
        make_doc("1", "블랙홀", text="[합성] 블랙홀은 빛도 못 빠져나오는 천체다. " * 5),
        movie_id="157336", related_movie="인터스텔라",
    )  # fmt: skip
    services.doc_indexer().index_document(doc)

    graph = build_graph(services.retriever(), llm, services.profile)
    state = graph.invoke({"movie_id": "157336", "question": "블랙홀은?", "task": "qa"})
    assert state["contexts"][0].source_kind == "meta"
    assert any(e.source_kind == "wiki" for e in state["contexts"])
    assert state["answer"].endswith("[근거 2].")
    assert len(llm.prompts_for("답변 생성")) == 1
    assert state["no_external"] is False


def test_tc_f2007_11_services_rag_graph(tmp_settings):
    llm = FakeChatModel(rules={"답변 생성": "[합성] 답 [근거 1]."})
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    state = services.rag_graph().invoke({"movie_id": "157336", "question": "q", "task": "qa"})
    assert state["contexts"][0].source_kind == "meta"
    assert state["answer"] == "[합성] 답 [근거 1]."
    assert state["no_external"] is True


def test_tc_f2007_11_prompt_contains_retrieved_evidence(tmp_settings):
    llm = FakeChatModel(rules={"답변 생성": "제공된 문서에서 확인되지 않습니다."})
    services = build_services(tmp_settings, llm=llm, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    doc = dataclasses.replace(
        make_doc("1", "블랙홀", text="[합성] 블랙홀은 빛도 못 빠져나오는 천체다. " * 5),
        movie_id="157336", related_movie="인터스텔라",
    )  # fmt: skip
    services.doc_indexer().index_document(doc)
    state = services.rag_graph().invoke(
        {"movie_id": "157336", "question": "블랙홀은?", "task": "qa"}
    )
    prompt = llm.prompts_for("답변 생성")[0]
    assert "블랙홀은 빛도 못 빠져나오는 천체다" in prompt and "(위키백과) 블랙홀" in prompt
    assert state["not_found"] is True
