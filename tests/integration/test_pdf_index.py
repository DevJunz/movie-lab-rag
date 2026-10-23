"""SPEC-F2016 PDF 색인 — 영화별 청크, 청크 ID에 쪽 번호, 청크가 쪽을 넘지 않음."""

from __future__ import annotations

import re

import pytest

from movielab.container import build_services
from movielab.data.pdf_source import PdfEntry, PdfPage
from tests.fakes import FakeEmbeddings

ENTRY = PdfEntry(
    doc_id="synth2014",
    file="synth.pdf",
    title="합성 보고서",
    source_url="https://example.invalid/synth.pdf",
    license="공공누리 제1유형",
    item_ids=("157336", "27205"),
)


def _pages() -> list[PdfPage]:
    return [
        PdfPage(number=n, text=" ".join(f"Page{n} sentence {i}." for i in range(120)))
        for n in (1, 2, 3)
    ]


@pytest.fixture
def services(tmp_settings):
    return build_services(tmp_settings, embeddings=FakeEmbeddings())


def test_tc_f2016_02_chunk_ids_per_movie_and_page(services):
    indexer = services.pdf_indexer()
    count = indexer.index_pdf(ENTRY, _pages())
    entries = services.store.entries("pdf_docs")
    assert count == len(entries) and count > 6  # 쪽마다 여러 청크 x 영화 2편

    pattern = re.compile(r"^(\d+):pdf:synth2014:(\d+):(\d+)$")
    pages = {p.number: p.text for p in _pages()}
    docs = services.store.get_by_ids("pdf_docs", [chunk_id for chunk_id, _ in entries])
    for doc in docs:
        match = pattern.match(doc.id)
        assert match, doc.id
        movie_id, page = match.group(1), int(match.group(2))
        assert doc.metadata["movie_id"] == movie_id
        assert doc.metadata["page"] == page
        assert doc.metadata["file"] == "synth.pdf"
        assert doc.metadata["source_kind"] == "pdf" and doc.metadata["source_type"] == "PDF"
        assert doc.page_content in pages[page]  # 청크가 쪽을 넘지 않는다
        assert len(doc.page_content) <= services.settings.chunking.pdf_chunk_size
    movies = {meta["movie_id"] for _, meta in entries}
    assert movies == {"157336", "27205"}


def test_tc_f2016_02_reindex_removes_stale_chunks(services):
    indexer = services.pdf_indexer()
    indexer.index_pdf(ENTRY, _pages())
    fewer = indexer.index_pdf(ENTRY, _pages()[:1])
    assert services.store.count("pdf_docs") == fewer
    assert all(":pdf:synth2014:1:" in chunk_id for chunk_id in services.store.ids("pdf_docs"))
