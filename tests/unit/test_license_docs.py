"""SPEC-NF2007 출처와 이용 조건 — README 기록 · 고지 문구 · 픽스처 합성 여부."""

from __future__ import annotations

import re
from pathlib import Path

from movielab.data.domain_movie import MOVIE_PROFILE

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    rest = text[start + len(heading) :]
    match = re.search(r"^## ", rest, flags=re.MULTILINE)
    return rest[: match.start()] if match else rest


def test_tc_nf2007_01_readme_source_section():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = _section(readme, "## 데이터 출처와 이용 조건")
    for needle in (
        "TMDB",
        "This product uses the TMDB API but is not endorsed or certified by TMDB.",
        "ko.wikipedia.org",
        "CC BY-SA 4.0",
        "https://creativecommons.org/licenses/by-sa/4.0/deed.ko",
        "2차 저작물",
        "원본",
        "2026-09",
    ):
        assert needle in section, needle


def test_tc_nf2007_04_attribution_notice():
    notice = MOVIE_PROFILE.attribution_notice
    for needle in ("TMDB", "한국어 위키백과", "CC BY-SA 4.0", "요약"):
        assert needle in notice, needle


def test_tc_nf2007_05_fixtures_are_synthetic():
    files = [p for p in FIXTURES.rglob("*") if p.is_file()]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "ko.wikipedia.org/wiki/" not in text, path.name
        if path.suffix == ".json" and path.parent.name.startswith("wiki"):
            assert "[합성]" in text, path.name
