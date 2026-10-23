"""SPEC-NF2004 §2.3 — 로깅 설정: 핸들러가 겹치지 않고, 비밀 값은 파일에 남지 않는다."""

from __future__ import annotations

import logging

import pytest

from movielab.core.logs import configure_logging

FAKE_KEY = "sk-test-abcdef1234567890"


@pytest.fixture
def clean_root():
    root = logging.getLogger()
    before = list(root.handlers)
    level = root.level
    yield root
    for handler in list(root.handlers):
        if handler not in before:
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)


def test_tc_nf2004_07_single_handler_and_masked_secrets(tmp_path, clean_root):
    options = {"max_bytes": 10_000, "backup_count": 1, "level": "INFO", "secrets": [FAKE_KEY]}
    log_file = tmp_path / "logs" / "movielab.log"
    configure_logging(log_file, **options)
    configure_logging(log_file, **options)
    ours = [h for h in clean_root.handlers if getattr(h, "movielab", False)]
    assert len(ours) == 1
    logger = logging.getLogger("movielab.test")
    logger.info("키가 섞인 메시지 %s", FAKE_KEY)
    try:
        raise RuntimeError(f"예외 안의 키 {FAKE_KEY}")
    except RuntimeError:
        logger.exception("실패")
    for handler in ours:
        handler.flush()
    text = log_file.read_text(encoding="utf-8")
    assert FAKE_KEY not in text
    assert "***" in text and "Traceback" in text  # traceback은 파일에 남는다
