"""설정 로드 (SPEC-NF2005 TC-09).

키 관리(NF2003) · 값 검증(F2005 등) 테스트는 각 SPEC PR에서 추가한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from movielab.config import load_settings
from tests.conftest import REPO_ROOT


def test_tc_nf2005_09_default_settings_file():
    settings = load_settings()
    assert settings.chunking.chunk_size == 1000  # D-04
    assert settings.chunking.chunk_overlap == 200
    assert settings.retrieval.top_k == 4
    assert settings.retrieval.search_type == "similarity"
    assert settings.models.chat == "gpt-4o-mini"  # D-05
    assert settings.models.embedding == "text-embedding-3-small"
    assert settings.collections.meta == "movie_meta"
    assert settings.collections.docs == "wiki_docs"
    assert settings.collect.source == "auto"  # A-17
    # 상대 경로는 저장소 루트 기준 절대 경로로 바뀐다
    assert settings.path("chroma_dir") == (REPO_ROOT / "data" / "chroma").resolve()


def test_tc_nf2005_09_env_selects_other_file(tmp_path: Path, monkeypatch):
    raw = json.loads((REPO_ROOT / "config" / "settings.json").read_text(encoding="utf-8"))
    raw["retrieval"]["top_k"] = 7
    other = tmp_path / "other.json"
    other.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setenv("MOVIELAB_SETTINGS", str(other))
    assert load_settings().retrieval.top_k == 7


def test_tc_nf2005_09_tmp_settings_points_into_tmp_path(tmp_settings, tmp_path: Path):
    assert tmp_settings.path("chroma_dir").is_relative_to(tmp_path)
    assert tmp_settings.path("manifest").is_relative_to(tmp_path)
    assert tmp_settings.path("movies").name == "movies_small.json"
