"""색인 작업 조율 — 스크립트는 이 함수로 Catalog(F2001)와 VectorStore(F2002)를 잇는다.

어떤 실패에서도 기존 색인을 잃지 않는 것이 원칙이다 (AC-F2002-07):
- 검사 · 로드 · 키 준비가 끝나기 전에는 아무것도 지우지 않는다.
- `rebuild`는 임시 컬렉션에 새로 만든 뒤, 모든 배치가 성공했을 때만 기존 것과 바꾼다.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import openai

from movielab.core.errors import DataEmptyError, InvalidApiKeyError
from movielab.core.types import IndexReport, ReindexReport, SourceDocument
from movielab.index.doc_indexer import DocIndexer
from movielab.index.meta_indexer import index_items
from movielab.index.store import VectorStore
from movielab.services.catalog import Catalog

logger = logging.getLogger(__name__)

REBUILD_SUFFIX = "__rebuild"


def index_catalog(
    catalog: Catalog,
    store: VectorStore,
    *,
    rebuild: bool = False,
    batch_size: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> IndexReport:
    """SPEC-F2002 §3.1: 검사 → 로드(0건이면 중단) → 키 준비 → upsert(또는 임시 컬렉션) → 정리."""
    settings = store.settings
    collection = settings.collections.meta
    indexing = settings.indexing
    size = indexing.batch_size if batch_size is None else batch_size
    if size < 1:
        raise ValueError(f"batch_size는 1 이상이어야 한다: {size}")

    items = catalog.items()
    if not items:
        raise DataEmptyError(f"불러온 항목이 0건이다 (건너뜀 {catalog.skipped}건)")
    _ = store.embeddings  # 키가 없으면 여기서 안내 오류

    target = f"{collection}{REBUILD_SUFFIX}" if rebuild else collection
    if rebuild:
        store.delete_collection(target)  # 이전에 실패하고 남은 임시 컬렉션
    try:
        failed = index_items(
            store,
            items,
            collection=target,
            batch_size=size,
            retries=indexing.retries,
            retry_wait_sec=indexing.retry_wait_sec,
            sleep=sleep,
        )
    except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
        if rebuild:
            store.delete_collection(target)
        raise InvalidApiKeyError(str(exc)) from exc
    except Exception:
        if rebuild:
            store.delete_collection(target)
        raise

    loaded_ids = {item.item_id for item in items}
    removed = 0
    if rebuild:
        if failed:
            logger.warning("rebuild 실패 배치 %s — 기존 색인을 유지한다", failed)
            store.delete_collection(target)
        else:
            store.delete_collection(collection)
            store.rename_collection(target, collection)
    elif not failed:
        orphans = [doc_id for doc_id in store.ids(collection) if doc_id not in loaded_ids]
        store.delete_ids(collection, orphans)
        removed = len(orphans)

    current_ids = store.ids(collection)
    return IndexReport(
        loaded=len(items) + catalog.skipped,
        skipped=catalog.skipped,
        indexed=sum(1 for doc_id in current_ids if doc_id in loaded_ids),
        failed_batches=failed,
        removed=removed,
    )


def reindex_documents(
    documents: list[SourceDocument], indexer: DocIndexer, *, movie_id: str | None = None
) -> ReindexReport:
    """저장된 원문으로 외부 문서 컬렉션을 다시 만든다 (F2005 §3.3).

    - 잘못된 키는 `InvalidApiKeyError`로 바꿔 바로 중단한다 (모든 문서가 같은 이유로 실패한다).
    - 그 밖의 오류는 그 문서만 실패로 세고 다음 문서로 넘어간다 — 실패한 문서의 옛 청크는 남는다.
    - 원문이 없는 문서의 청크는 지운다. `movie_id`를 주면 그 항목 범위에서만.
    """
    chunks = failed = 0
    for doc in documents:
        try:
            chunks += indexer.index_document(doc)
        except (openai.AuthenticationError, openai.PermissionDeniedError) as exc:
            raise InvalidApiKeyError(str(exc)) from exc
        except Exception:
            logger.exception("재색인 실패: %s/%s", doc.movie_id, doc.page_id)
            failed += 1

    keep = {(str(doc.movie_id), str(doc.page_id)) for doc in documents}
    orphans = sorted(indexer.indexed_pages(movie_id) - keep)
    for orphan_item, page_id in orphans:
        indexer.delete_document(orphan_item, page_id)
    return ReindexReport(
        documents=len(documents),
        chunks=chunks,
        failed=failed,
        removed=len(orphans),
        total_chunks=indexer.store.count(indexer.collection),
    )
