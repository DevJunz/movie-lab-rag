"""SPEC-F2016 PDF 소스 — 쪽별 추출, 반복 머리말 · 꼬리말 제거, 하이픈 줄바꿈, 빈 쪽 건너뜀."""

from __future__ import annotations

import json

import pytest

from movielab.data.pdf_source import PdfEntry, extract_pages, load_pdf_manifest
from tests.fakes.pdf import write_pdf

HEADER = "MOVIELAB SYNTHETIC REPORT 2014"
FOOTER = "Synthetic test document - not real data"


def _body(n: int) -> list[str]:
    return [
        f"Page {n} body text about box office numbers and audience trends.",
        f"Synthetic paragraph {n} continues with more words for the test.",
    ]


def test_tc_f2016_01_pages_with_repeated_header_removed(tmp_path):
    pages = [[HEADER, *_body(n), FOOTER] for n in (1, 2, 3)]
    pages[1].insert(2, "The cine-")
    pages[1].insert(3, "matography was praised.")
    path = write_pdf(tmp_path / "report.pdf", pages)

    result = extract_pages(path, min_page_chars=50, repeat_line_min_pages=3)

    assert [p.number for p in result.pages] == [1, 2, 3]
    assert result.skipped_pages == []
    for page in result.pages:
        assert HEADER not in page.text and FOOTER not in page.text
        assert f"Page {page.number} body text" in page.text
    assert "cinematography was praised." in result.pages[1].text


def test_tc_f2016_01_header_kept_when_fewer_pages_than_threshold(tmp_path):
    path = write_pdf(tmp_path / "two.pdf", [[HEADER, *_body(1)], [HEADER, *_body(2)]])
    result = extract_pages(path, min_page_chars=50, repeat_line_min_pages=3)
    assert all(HEADER in p.text for p in result.pages)


def test_tc_f2016_06_textless_page_skipped_and_reported(tmp_path):
    pages = [[HEADER, *_body(1)], [], ["tiny"], [HEADER, *_body(4)]]
    path = write_pdf(tmp_path / "scan.pdf", pages)
    result = extract_pages(path, min_page_chars=50, repeat_line_min_pages=3)
    assert [p.number for p in result.pages] == [1, 4]
    assert result.skipped_pages == [2, 3]


def test_tc_f2016_02_manifest_loaded(tmp_path):
    manifest = tmp_path / "pdf_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "doc_id": "synth2014",
                    "file": "synth.pdf",
                    "title": "합성 보고서",
                    "source_url": "https://example.invalid/synth.pdf",
                    "license": "공공누리 제1유형",
                    "movie_ids": [157336, "27205"],
                    "pages": "all",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    entries = load_pdf_manifest(manifest)
    assert entries == [
        PdfEntry(
            doc_id="synth2014",
            file="synth.pdf",
            title="합성 보고서",
            source_url="https://example.invalid/synth.pdf",
            license="공공누리 제1유형",
            item_ids=("157336", "27205"),
        )
    ]


@pytest.mark.parametrize(
    "content", ["[{깨진", '{"doc_id": "x"}', '[{"doc_id": "x", "file": "a.pdf"}]']
)
def test_tc_f2016_02_bad_manifest_raises(tmp_path, content):
    manifest = tmp_path / "pdf_manifest.json"
    manifest.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_pdf_manifest(manifest)
