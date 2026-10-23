"""SPEC-F2002 TC-07 — 실제 GMS 임베딩으로 영화 3편 색인 (`pytest -m live`)."""

from __future__ import annotations

import pytest

from movielab.config import load_settings
from movielab.container import build_services
from movielab.index.meta_indexer import index_items

pytestmark = pytest.mark.live


def test_tc_f2002_07_real_embeddings_index_three(tmp_path, movies_small_path):
    settings = load_settings()
    settings.raw["paths"] = {
        **settings.raw["paths"],
        "chroma_dir": str(tmp_path / "chroma"),
        "movies": str(movies_small_path),
    }
    services = build_services(settings)
    items = services.catalog.items()[:3]
    failed = index_items(
        services.store, items, collection="movie_meta", batch_size=100, retries=1, retry_wait_sec=2
    )
    assert failed == []
    assert services.store.count("movie_meta") == 3
