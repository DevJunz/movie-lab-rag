"""SPEC-NF2004 AC-05 — Streamlit 오류 상세 표시를 끈다."""

from __future__ import annotations

import toml

from tests.conftest import REPO_ROOT


def test_tc_nf2004_05_error_details_hidden():
    config = toml.loads((REPO_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8"))
    assert config["client"]["showErrorDetails"] == "none"
