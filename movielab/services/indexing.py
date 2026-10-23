"""색인 작업 조율 — 스크립트는 이 함수로 Catalog(F2001)와 VectorStore(F2002)를 잇는다.

어떤 실패에서도 기존 색인을 잃지 않는 것이 원칙이다 (AC-F2002-07):
- 검사 · 로드 · 키 준비가 끝나기 전에는 아무것도 지우지 않는다.
- `rebuild`는 임시 컬렉션에 새로 만든 뒤, 모든 배치가 성공했을 때만 기존 것과 바꾼다.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import openai

from movielab.core.errors import DataEmptyError, InvalidApiKeyError, MovieLabUserError
from movielab.core.types import IndexReport, ReindexReport, SourceDocument
from movielab.index.doc_indexer import DocIndexer
from movielab.index.meta_indexer import UNRECOVERABLE, index_items
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
    store.ensure_embeddings()  # 키가 없으면 여기서 안내 오류

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
    documents: list[SourceDocument],
    indexer: DocIndexer,
    *,
    movie_id: str | None = None,
    manifest: Any = None,
    unreadable: set[tuple[str, str]] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ReindexReport:
    """저장된 원문으로 외부 문서 컬렉션을 다시 만든다 (F2005 §3.3).

    - 다시 색인할 원문이 있으면 시작 전에 임베딩(키)을 준비한다. 안내 오류(키 없음 · 잘못된 키)는
      바로 중단한다. 원문이 없으면(고아 정리만) 키 없이 동작한다.
    - 그 밖의 오류는 설정 횟수만큼 다시 시도하고(A-21), 그래도 실패하면 그 문서만 실패로 센다
      — 실패한 문서의 옛 청크는 남는다. 재시도 분류는 메타 색인(F2002)과 같다: `UNRECOVERABLE`은
      재시도하지 않고, 응답이 잘려 나는 `JSONDecodeError`는 일시 오류로 보고 재시도한다.
    - 원문이 없는 문서의 청크는 지운다. `movie_id`를 주면 그 항목 범위에서만.
      청크를 지운 영화는 수집 매니페스트(`manifest`)도 초기화해 다음 질문에서 다시 수집되게 한다.
    """
    if documents:
        indexer.store.ensure_embeddings()  # 키가 없으면 여기서 안내 오류
    indexing = indexer.store.settings.indexing
    succeeded = chunks = failed = 0
    for doc in documents:
        done = False
        for attempt in range(indexing.retries + 1):
            try:
                chunks += indexer.index_document(doc)
                succeeded += 1
                done = True
                break
            except MovieLabUserError:
                raise
            except json.JSONDecodeError:  # 응답이 잘림 — 일시 오류
                logger.exception("재색인 응답 해석 실패 (%d번째): %s", attempt + 1, doc.page_id)
                if attempt < indexing.retries:
                    sleep(indexing.retry_wait_sec)
                continue
            except UNRECOVERABLE:
                logger.exception("재색인 실패 (재시도 안 함): %s/%s", doc.movie_id, doc.page_id)
                break
            except Exception:
                logger.exception(
                    "재색인 실패 (%d/%d): %s/%s",
                    attempt + 1,
                    indexing.retries + 1,
                    doc.movie_id,
                    doc.page_id,
                )
                if attempt < indexing.retries:
                    sleep(indexing.retry_wait_sec)
        if not done:
            failed += 1

    # 읽지 못한 원문의 문서는 실패로 세고 청크는 지우지 않는다
    unreadable = unreadable or set()
    failed += len(unreadable)
    keep = {(str(doc.movie_id), str(doc.page_id)) for doc in documents} | unreadable
    orphans = indexer.prune(keep, movie_id)
    if manifest is not None:
        for orphan_item in sorted({item for item, _ in orphans}):
            manifest.reset(orphan_item)
    return ReindexReport(
        documents=succeeded,
        chunks=chunks,
        failed=failed,
        removed=len(orphans),
        total_chunks=indexer.store.count(indexer.collection),
    )
