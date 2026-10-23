"""로깅 설정 — `logs/movielab.log` 회전 파일, 비밀 값 가림 (SPEC-NF2004 §2.3).

앱과 스크립트가 시작할 때 한 번 부른다. 여러 번 불러도 핸들러가 겹치지 않는다.
예외 메시지 · traceback은 이 파일에만 남고 화면에는 나가지 않는다.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _MaskSecrets(logging.Formatter):
    """기록 직전의 완성된 문장(traceback 포함)에서 비밀 값을 `***`로 바꾼다."""

    def __init__(self, secrets: list[str]) -> None:
        super().__init__(_FORMAT)
        self.secrets = [s for s in secrets if s]

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        for secret in self.secrets:
            text = text.replace(secret, "***")
        return text


def configure_logging(
    log_file: Path,
    *,
    max_bytes: int,
    backup_count: int,
    level: str,
    secrets: list[str],
) -> None:
    """루트 로거에 회전 파일 핸들러를 하나만 붙인다 (이미 있으면 바꾼다)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "movielab", False):
            root.removeHandler(handler)
            handler.close()
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    handler.setFormatter(_MaskSecrets(secrets))
    handler.movielab = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)


def configure_from_settings(settings: Any) -> None:
    """설정(`paths.log_file`, `logging`)과 비밀 값(`secrets`)으로 로깅을 켠다."""
    options = settings.logging
    secrets = settings.secrets
    configure_logging(
        settings.path("log_file"),
        max_bytes=options.max_bytes,
        backup_count=options.backup_count,
        level=options.level,
        secrets=[v for v in (secrets.gms_api_key, secrets.gms_base_url, secrets.wiki_contact) if v],
    )
