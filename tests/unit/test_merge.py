"""SPEC-F2006 TC-04 — 병합 · 중복 제거 · 번호 부여."""

from __future__ import annotations

from movielab.core.types import Evidence
from movielab.rag.retriever import merge_evidences


def _e(chunk_id, text, kind="wiki", score=0.5):
    return Evidence(
        n=0, chunk_id=chunk_id, source_kind=kind, source_type="위키백과", title=chunk_id,
        url="https://x", license=None, text=text, score=score,
    )  # fmt: skip


def test_tc_f2006_04_dedupe_by_id_and_text_then_number():
    meta = _e("157336", "메타 본문", kind="meta", score=None)
    merged = merge_evidences(
        [meta],
        [
            _e("157336:1:0", "블랙홀 문단"),
            _e("157336:1:0", "블랙홀 문단"),  # 같은 ID
            _e("157336:2:0", "블랙홀   문단 "),  # 공백만 다른 같은 본문
            _e("157336:3:0", "웜홀 문단"),
        ],
    )
    assert [e.chunk_id for e in merged] == ["157336", "157336:1:0", "157336:3:0"]
    assert [e.n for e in merged] == [1, 2, 3]
