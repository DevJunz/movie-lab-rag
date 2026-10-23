"""시작 점검 — 키가 있는지 · 색인 건수 (SPEC-F2012 §3.2).

키는 **값이 있는지만** 본다. 화면에 키 값 · 일부 · 길이를 내보내지 않는다(NF2004).
건수는 임베딩(키) 없이 읽는다 — 키가 없어도 안내 화면을 그릴 수 있어야 한다.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HealthStatus:
    api_key_ok: bool
    meta_count: int
    docs_count: int


def check(settings: Any, store: Any) -> HealthStatus:
    """`settings.secrets.has_gms`와 `store.count(컬렉션)`. 색인을 읽지 못하면 건수는 0."""
    collections = settings.collections
    try:
        meta_count = store.count(collections.meta)
        docs_count = store.count(collections.docs)
    except Exception:
        logger.exception("색인 건수를 읽지 못했다")
        meta_count = docs_count = 0
    return HealthStatus(
        api_key_ok=settings.secrets.has_gms, meta_count=meta_count, docs_count=docs_count
    )
