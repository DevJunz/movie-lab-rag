"""색인 작업 조율 — 스크립트는 이 함수로 Catalog(F2001)와 VectorStore(F2002)를 잇는다."""

from __future__ import annotations

import time
from collections.abc import Callable

from movielab.core.types import IndexReport
from movielab.index.meta_indexer import index_items
from movielab.index.store import VectorStore
from movielab.services.catalog import Catalog


def index_catalog(
    catalog: Catalog,
    store: VectorStore,
    *,
    rebuild: bool = False,
    batch_size: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> IndexReport:
    """SPEC-F2002 §3.1 순서: 항목 로드 → 임베딩(키) 확인 → (rebuild면 삭제) → upsert → 고아 삭제."""
    settings = store.settings
    collection = settings.collections.meta
    indexing = settings.indexing
    items = catalog.items()
    _ = store.embeddings  # 키가 없으면 여기서 안내 오류 — 기존 색인을 지우기 전에 확인한다
    if rebuild:
        store.delete_collection(collection)
    failed = index_items(
        store,
        items,
        collection=collection,
        batch_size=batch_size or indexing.batch_size,
        retries=indexing.retries,
        retry_wait_sec=indexing.retry_wait_sec,
        sleep=sleep,
    )
    loaded_ids = {item.item_id for item in items}
    removed = 0
    if not failed:
        orphans = [doc_id for doc_id in store.ids(collection) if doc_id not in loaded_ids]
        store.delete_ids(collection, orphans)
        removed = len(orphans)
    indexed = sum(1 for doc_id in store.ids(collection) if doc_id in loaded_ids)
    return IndexReport(
        loaded=len(items) + catalog.skipped,
        skipped=catalog.skipped,
        indexed=indexed,
        failed_batches=failed,
        removed=removed,
    )
