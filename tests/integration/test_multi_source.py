"""SPEC-F2016 위키 + PDF 결합 검색 · 근거 표시 · PDF 없을 때 MVP 동작."""

from __future__ import annotations

import dataclasses
import json

import pytest

from movielab.container import build_services
from movielab.core import messages
from movielab.core.types import Evidence
from movielab.data.pdf_source import PdfEntry, PdfPage
from movielab.services.indexing import index_catalog
from tests.fakes import FakeClock, FakeEmbeddings
from tests.fakes.pdf import write_pdf
from tests.fakes.source import make_doc

QUESTION = "black hole event horizon"

ENTRY = PdfEntry(
    doc_id="synth2014",
    file="synth.pdf",
    title="합성 보고서",
    source_url="https://example.invalid/synth.pdf",
    license="공공누리 제1유형",
    item_ids=("157336",),
)


@pytest.fixture
def services(tmp_settings):
    services = build_services(tmp_settings, embeddings=FakeEmbeddings())
    index_catalog(services.catalog, services.store, sleep=FakeClock().sleep)
    return services


def _index_wiki(services):
    indexer = services.doc_indexer()
    for page_id, text in (
        ("1", "black hole event horizon wiki article text. " * 4),
        ("2", "wormhole travel wiki article text. " * 4),
    ):
        doc = dataclasses.replace(make_doc(page_id, f"wiki{page_id}", text=text), movie_id="157336")
        indexer.index_document(doc)


def _index_pdf(services):
    pages = [
        PdfPage(number=12, text="black hole event horizon box office report page. " * 3),
        PdfPage(number=13, text="unrelated audience survey numbers and tables. " * 3),
    ]
    services.pdf_indexer().index_pdf(ENTRY, pages)


def test_tc_f2016_03_wiki_and_pdf_retrieved_together(services):
    _index_wiki(services)
    _index_pdf(services)
    result = services.retriever().retrieve("157336", QUESTION)
    kinds = [e.source_kind for e in result.evidences]
    assert kinds[0] == "meta" and result.evidences[0].n == 1
    assert "wiki" in kinds and "pdf" in kinds
    assert kinds.count("pdf") <= services.settings.retrieval.pdf_top_k
    assert [e.n for e in result.evidences] == list(range(1, len(result.evidences) + 1))
    externals = [e.score for e in result.evidences[1:]]
    assert externals == sorted(externals, reverse=True)  # 위키 · PDF를 점수 순으로 섞는다
    pdf = next(e for e in result.evidences if e.source_kind == "pdf")
    assert pdf.page == 12 and pdf.file == "synth.pdf" and pdf.source_type == "PDF"
    assert pdf.license == "공공누리 제1유형" and pdf.url == "https://example.invalid/synth.pdf"


def test_tc_f2016_04_pdf_evidence_display():
    evidence = Evidence(
        n=3,
        chunk_id="157336:pdf:synth2014:12:0",
        source_kind="pdf",
        source_type=messages.PDF_SOURCE_LABEL,
        title="합성 보고서",
        url="https://example.invalid/synth.pdf",
        license="공공누리 제1유형",
        text="본문",
        page=12,
        file="synth.pdf",
    )
    assert messages.PDF_SOURCE_LABEL == "PDF"
    assert messages.evidence_title(evidence) == "합성 보고서 (synth.pdf, p.12)"
    wiki = dataclasses.replace(evidence, source_kind="wiki", page=None, file=None, title="블랙홀")
    assert messages.evidence_title(wiki) == "블랙홀"


def test_tc_f2016_04_script_evidence_list_shows_pdf(services, capsys):
    from scripts.collect import _print_evidence

    _index_wiki(services)
    _index_pdf(services)
    _print_evidence(services.retriever().retrieve("157336", QUESTION))
    out = capsys.readouterr().out
    assert "PDF · 합성 보고서 (synth.pdf, p.12)" in out
    assert "위키백과 · " in out and "[근거 1] 영화 메타데이터 · " in out


def test_tc_f2016_05_empty_pdf_collection_same_as_mvp(services):
    _index_wiki(services)
    with_pdf_setting = services.retriever().retrieve("157336", QUESTION)
    mvp = services.retriever(pdf_top_k=0).retrieve("157336", QUESTION)
    assert with_pdf_setting == mvp
    assert all(e.source_kind != "pdf" for e in mvp.evidences)


def test_tc_f2016_05_other_movie_pdf_not_used(services):
    _index_wiki(services)
    services.pdf_indexer().index_pdf(
        dataclasses.replace(ENTRY, item_ids=("27205",)),
        [PdfPage(number=1, text="black hole event horizon report. " * 3)],
    )
    result = services.retriever().retrieve("157336", QUESTION)
    assert all(e.source_kind != "pdf" for e in result.evidences)


def test_tc_f2016_02_index_pdf_script(tmp_settings, monkeypatch, capsys):
    from scripts import index_pdf

    pdf_dir = tmp_settings.path("pdf_dir")
    body = ["Synthetic page text about black hole event horizon and box office numbers."]
    write_pdf(pdf_dir / "synth.pdf", [body, [], body])
    tmp_settings.path("pdf_manifest").write_text(
        json.dumps(
            [
                {
                    "doc_id": "synth2014",
                    "file": "synth.pdf",
                    "title": "합성 보고서",
                    "source_url": "https://example.invalid/synth.pdf",
                    "license": "공공누리 제1유형",
                    "movie_ids": ["157336"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    real_build = index_pdf.build_services
    monkeypatch.setattr(
        index_pdf, "build_services", lambda s: real_build(s, embeddings=FakeEmbeddings())
    )
    assert index_pdf.main([]) == 0
    out = capsys.readouterr().out
    assert "synth.pdf" in out and "2" in out  # 건너뛴 쪽 번호
    ids = build_services(tmp_settings, embeddings=FakeEmbeddings()).store.ids("pdf_docs")
    assert sorted(ids) == ["157336:pdf:synth2014:1:0", "157336:pdf:synth2014:3:0"]


def test_tc_f2016_05_index_pdf_script_without_manifest(tmp_settings, monkeypatch, capsys):
    from scripts import index_pdf

    monkeypatch.setenv("MOVIELAB_SETTINGS", str(tmp_settings.source))
    assert index_pdf.main([]) == 1
    out = capsys.readouterr().out
    assert "pdf_manifest" in out and "Traceback" not in out


def test_tc_f2016_04_ui_evidence_line_shows_pdf():
    from movielab.data.domain_movie import MOVIE_PROFILE
    from movielab.ui.components.evidence import evidence_line

    evidence = Evidence(
        n=3,
        chunk_id="157336:pdf:synth2014:12:0",
        source_kind="pdf",
        source_type=messages.PDF_SOURCE_LABEL,
        title="합성 보고서",
        url="https://example.invalid/synth.pdf",
        license="공공누리 제1유형",
        text="본문",
        page=12,
        file="synth.pdf",
    )
    line = evidence_line(evidence, MOVIE_PROFILE)
    assert line.startswith("**[근거 3]** PDF · 합성 보고서 (synth.pdf, p.12) · [원문 ↗](")
    assert line.endswith(" · 공공누리 제1유형")
