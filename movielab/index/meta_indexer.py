"""항목 메타데이터 색인 (RAG 1, SPEC-F2002). 항목 1건 = 청크 1개, 청크 ID = 항목 ID."""

from __future__ import annotations

import logging

from langchain_core.documents import Document

from movielab.core.errors import MovieLabUserError
from movielab.core.types import ItemRecord
from movielab.index.store import VectorStore

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100
RETRIES = 1  # 배치 하나당 재시도 횟수


def _document(item: ItemRecord) -> Document:
    return Document(page_content=item.index_text, metadata=dict(item.metadata), id=item.item_id)


def index_items(
    store: VectorStore,
    items: list[ItemRecord],
    *,
    collection: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[int]:
    """배치로 나눠 upsert 한다. 재시도 후에도 실패한 배치 번호(0부터)를 돌려준다.

    실패한 배치가 있어도 나머지 배치는 넣는다 — 다시 실행하면 빠진 것만 채워진다.
    """
    failed: list[int] = []
    for number, start in enumerate(range(0, len(items), batch_size)):
        batch = items[start : start + batch_size]
        for attempt in range(RETRIES + 1):
            try:
                store.upsert(collection, [_document(i) for i in batch], [i.item_id for i in batch])
                break
            except MovieLabUserError:
                raise  # 키 없음 등 안내가 필요한 오류는 재시도하지 않고 그대로 알린다
            except Exception:
                logger.exception("메타 색인 배치 %d 실패 (시도 %d)", number, attempt + 1)
        else:
            failed.append(number)
    return failed
