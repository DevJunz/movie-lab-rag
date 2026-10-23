"""PDF 문서 소스 (SPEC-F2016 §2.1 · §2.2).

- 매니페스트(`pdf_manifest.json`)에서 PDF 목록 · 출처 · 이용 조건 · 근거로 쓸 영화를 읽는다.
- `pypdf`로 쪽별 텍스트를 뽑고, 여러 쪽에 반복되는 머리말 · 꼬리말 줄을 지우고, 하이픈 줄바꿈을
  잇는다. 텍스트가 거의 없는 쪽(스캔 이미지 등)은 건너뛰고 쪽 번호를 보고한다(OCR은 범위 밖).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfReader

_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_REQUIRED = ("doc_id", "file", "title", "source_url", "license", "movie_ids")


@dataclass(frozen=True)
class PdfEntry:
    """매니페스트 1건. `item_ids`는 이 PDF를 근거로 쓸 영화 ID(문자열)."""

    doc_id: str
    file: str
    title: str
    source_url: str
    license: str
    item_ids: tuple[str, ...]


@dataclass(frozen=True)
class PdfPage:
    number: int  # 1부터
    text: str


@dataclass(frozen=True)
class PdfText:
    pages: list[PdfPage] = field(default_factory=list)
    skipped_pages: list[int] = field(default_factory=list)  # 텍스트가 거의 없어 건너뛴 쪽


def _entry(raw: Any) -> PdfEntry:
    if not isinstance(raw, dict) or any(key not in raw for key in _REQUIRED):
        raise ValueError(f"PDF 매니페스트 항목에 필수 키({', '.join(_REQUIRED)})가 없다")
    item_ids = raw["movie_ids"]
    if not isinstance(item_ids, list) or not item_ids:
        raise ValueError(f"movie_ids는 비어 있지 않은 목록이어야 한다: {raw['doc_id']}")
    return PdfEntry(
        doc_id=str(raw["doc_id"]),
        file=str(raw["file"]),
        title=str(raw["title"]),
        source_url=str(raw["source_url"]),
        license=str(raw["license"]),
        item_ids=tuple(str(item_id) for item_id in item_ids),
    )


def load_pdf_manifest(path: Path) -> list[PdfEntry]:
    """매니페스트를 읽는다. 파일이 없으면 `FileNotFoundError`, 형식 오류는 `ValueError`."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"PDF 매니페스트 형식 오류: {exc.msg}") from exc
    if not isinstance(raw, list):
        raise ValueError("PDF 매니페스트는 JSON 배열이어야 한다")
    return [_entry(item) for item in raw]


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def extract_pages(path: Path, *, min_page_chars: int, repeat_line_min_pages: int) -> PdfText:
    """쪽별 텍스트. 반복 줄 판정은 `repeat_line_min_pages`쪽 이상에 같은 줄이 있을 때."""
    reader = PdfReader(str(path))
    raw_pages = [_lines(page.extract_text() or "") for page in reader.pages]
    counts = Counter(line for lines in raw_pages for line in set(lines))
    repeated = {line for line, count in counts.items() if count >= repeat_line_min_pages}
    pages: list[PdfPage] = []
    skipped: list[int] = []
    for number, lines in enumerate(raw_pages, start=1):
        text = "\n".join(line for line in lines if line not in repeated)
        text = _HYPHEN_BREAK.sub(r"\1\2", text)
        if len("".join(text.split())) < min_page_chars:
            skipped.append(number)
            continue
        pages.append(PdfPage(number=number, text=text))
    return PdfText(pages=pages, skipped_pages=skipped)
