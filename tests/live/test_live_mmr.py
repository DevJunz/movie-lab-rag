"""SPEC-F2014 TC-06 — 실제 색인 · GMS 임베딩으로 Q1 · Q2 유사도 / MMR 비교 (`pytest -m live`).

실제 색인(`data/chroma`)에 Q1 · Q2 문서가 수집되어 있어야 한다. 없으면 건너뛴다.
"""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.container import build_services

pytestmark = pytest.mark.live

CASES = [
    ("157336", "인터스텔라의 블랙홀 묘사는 실제 물리와 얼마나 다른가?", "인터스텔라"),
    pytest.param(
        "282631",
        "명량 해전에서 조선 수군의 배는 실제로 몇 척이었나?",
        "명량해협",
        # 현재 색인에서 「명량해협」은 유사도 20위(fetch_k 경계)라 λ=0.5로는 뽑히지 않는다 (SPEC §8)
        marks=pytest.mark.xfail(reason="SPEC-F2014 §8: 현재 색인에서 재현되지 않음", strict=False),
    ),
]


@pytest.mark.parametrize(("movie_id", "question", "title"), CASES)
def test_tc_f2014_06_mmr_brings_diverse_chunk(movie_id, question, title):
    services = build_services(load_settings())
    docs = services.settings.collections.docs
    if not services.store.has_where(docs, {"movie_id": movie_id}):
        pytest.skip(f"{movie_id} 외부 문서가 색인되어 있지 않다")
    titles = {}
    for kind in ("similarity", "mmr"):
        result = services.retriever(search_type=kind).retrieve(movie_id, question)
        titles[kind] = [e.title for e in result.evidences if e.source_kind != "meta"]
        print(kind, titles[kind])
    assert title in titles["mmr"]
