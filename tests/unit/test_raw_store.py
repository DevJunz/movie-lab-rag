"""SPEC-F2004 TC-18 — 수집 원문 저장 (01-architecture §4.2 형식)."""

from __future__ import annotations

import dataclasses
import json

from movielab.data.raw_store import RawStore
from tests.fakes.source import make_doc

FIELDS = {"page_id", "title", "url", "text", "source", "movie_id", "related_movie"}
FIELDS |= {"search_query", "collected_at"}


def test_tc_f2004_18_save_and_load_roundtrip(tmp_path):
    store = RawStore(tmp_path / "raw")
    doc = dataclasses.replace(
        make_doc("20671", "블랙홀"), movie_id="157336", related_movie="인터스텔라",
        search_query="블랙홀", is_item_doc=False,
    )  # fmt: skip
    path = store.save(doc)
    assert path == tmp_path / "raw" / "wiki" / "157336_20671.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert FIELDS <= set(data)
    assert data["page_id"] == "20671" and data["license"] == "CC BY-SA 4.0"
    assert store.load("157336", "20671") == doc
    assert store.load("157336", "없음") is None
