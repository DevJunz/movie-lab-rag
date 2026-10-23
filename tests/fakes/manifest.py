"""가짜 매니페스트.

- `RecordingManifest`: 기록 호출을 남긴다 (캐시 기록 시점 검사용).
- `make_manifest`: 실제 시간을 쓰지 않는 매니페스트
  (수치는 `config/settings.json`의 `cache`, 시계는 `FakeClock`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from movielab.collect.manifest import Manifest, NullManifest
from movielab.config import load_settings
from tests.fakes.clock import FakeClock

_SETTINGS = Path(__file__).resolve().parents[2] / "config" / "settings.json"


class RecordingManifest(NullManifest):
    def __init__(self) -> None:
        self.keywords: list[str] = []
        self.pages: list[tuple[str, int]] = []
        self.questions: list[str] = []

    def record_keyword(self, item_id: str, query: str) -> bool:
        self.keywords.append(query)
        return True

    def record_page(self, item_id, page_id, title, chunks, *, rejected=False) -> bool:
        self.pages.append((str(page_id), chunks))
        return True

    def record_question(self, item_id, question, queries) -> bool:
        self.questions.append(question)
        return True


_CACHE_KEYS = ("lock_timeout_sec", "lock_poll_sec", "io_retries", "io_retry_wait_sec")


def cache_settings() -> dict[str, Any]:
    """기본 설정 파일의 `cache` 묶음 — `load_settings`로 읽어 설정 검증을 거친다."""
    cache = load_settings(_SETTINGS).cache
    return {key: getattr(cache, key) for key in _CACHE_KEYS}


def make_manifest(path: Path, **overrides: Any) -> Manifest:
    """실제 시간을 쓰지 않는 매니페스트. `clock` · `sleep`을 주지 않으면 새 `FakeClock`을 쓴다."""
    options: dict[str, Any] = cache_settings()
    if "clock" not in overrides and "sleep" not in overrides:
        clock = FakeClock()
        options.update(clock=clock.monotonic, sleep=clock.sleep)
    options.update(overrides)
    return Manifest(path, **options)
