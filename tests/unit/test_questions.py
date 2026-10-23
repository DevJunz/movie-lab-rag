"""SPEC-NF2001 TC-07 — 대표 질문 목록이 00-product-overview §3 표와 같다."""

from __future__ import annotations

import json
import re

from tests.conftest import REPO_ROOT


def test_tc_nf2001_07_questions_match_overview():
    questions = json.loads(
        (REPO_ROOT / "docs" / "verification" / "questions.json").read_text(encoding="utf-8")
    )
    overview = (REPO_ROOT / "docs" / "spec" / "00-product-overview.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| (Q\d) \| [^|]*\((\d+)\) \| ([^|]+) \|", overview, flags=re.M)
    assert [q["id"] for q in questions] == [f"Q{n}" for n in range(1, 7)]
    expected = {qid: (movie_id, text.strip()) for qid, movie_id, text in rows}
    for q in questions:
        assert set(q) >= {"id", "movie_id", "question", "purpose"}
        assert isinstance(q["movie_id"], str)
        assert expected[q["id"]] == (q["movie_id"], q["question"])
