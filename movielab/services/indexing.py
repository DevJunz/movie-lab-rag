"""색인 작업 조율 — 스크립트는 이 함수로 Catalog(F2001)와 VectorStore(F2002)를 잇는다."""

from __future__ import annotations

from typing import Any

from movielab.core.types import IndexReport
from movielab.index.meta_indexer import DEFAULT_BATCH_SIZE, index_items
from movielab.index.store import VectorStore
from movielab.services.catalog import Catalog


def index_catalog(
    catalog: Catalog,
    store: VectorStore,
    settings: Any,
    *,
    rebuild: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> IndexReport:
    collection = settings.collections.meta
    items = catalog.items()
    if rebuild:
        store.delete_collection(collection)
    failed = index_items(store, items, collection=collection, batch_size=batch_size)
    return IndexReport(
        loaded=len(items) + catalog.skipped,
        skipped=catalog.skipped,
        indexed=store.count(collection),
        failed_batches=failed,
    )
