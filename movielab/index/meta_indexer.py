"""항목 메타데이터 색인 (RAG 1, SPEC-F2002). 항목 1건 = 청크 1개, 청크 ID = 항목 ID."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import openai
from langchain_core.documents import Document

from movielab.core.errors import MovieLabUserError
from movielab.core.types import ItemRecord
from movielab.index.store import VectorStore

logger = logging.getLogger(__name__)

# 다시 해도 같은 결과인 오류 — 재시도하지 않고 바로 알린다 (SPEC-F2002 §3.1-5)
UNRECOVERABLE = (
    MovieLabUserError,
    openai.AuthenticationError,
    openai.PermissionDeniedError,
    openai.BadRequestError,
    openai.NotFoundError,
    ValueError,
    TypeError,
)


def _document(item: ItemRecord) -> Document:
    return Document(page_content=item.index_text, metadata=dict(item.metadata), id=item.item_id)


def index_items(
    store: VectorStore,
    items: list[ItemRecord],
    *,
    collection: str,
    batch_size: int,
    retries: int,
    retry_wait_sec: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[int]:
    """배치로 나눠 upsert 한다. 재시도 후에도 실패한 배치 번호(0부터)를 돌려준다.

    실패한 배치가 있어도 나머지 배치는 넣는다 — 다시 실행하면 빠진 것만 채워진다.
    """
    if batch_size < 1:
        raise ValueError(f"batch_size는 1 이상이어야 한다: {batch_size}")
    failed: list[int] = []
    for number, start in enumerate(range(0, len(items), batch_size)):
        documents = [_document(item) for item in items[start : start + batch_size]]
        for attempt in range(retries + 1):
            try:
                store.upsert(collection, documents)
                break
            except UNRECOVERABLE:
                raise
            except Exception:
                logger.exception("메타 색인 배치 %d 실패 (시도 %d)", number, attempt + 1)
                if attempt < retries:
                    sleep(retry_wait_sec)
        else:
            failed.append(number)
    return failed
